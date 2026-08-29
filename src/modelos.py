"""
Modelos predictivos del rendimiento (pregunta P4): se puede predecir la marca
de una atleta, y que la determina.

La validacion es temporal, no aleatoria: se entrena con las competiciones hasta
2022 y se valida con 2023-2026. Un reparto aleatorio dejaria filas de la misma
atleta a ambos lados y el modelo acertaria por reconocerla.

Se excluye toda variable que contenga la respuesta (los tres levantamientos
suman el total; DOTS, Wilks y la fuerza relativa son funciones del total) y toda
medida tomada durante la propia competicion que se quiere predecir. La lista
esta en FUGA y se comprueba con una asersion.

Se comparan cuatro modelos: la media como referencia minima, una regresion
Ridge, gradient boosting con variables de perfil y gradient boosting anadiendo
las marcas anteriores. Los dos ultimos se evaluan sobre el mismo conjunto de
prueba, para que la diferencia mida solo lo que aporta la trayectoria.

La importancia se calcula por permutacion, que es fiable cuando hay variables
correlacionadas; la importancia interna del arbol se sesga hacia las variables
de alta cardinalidad.

Ejecucion:  python src/modelos.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
import estilo

estilo.aplicar()
RES: dict = {}

OBJETIVO = "total_kg"
ANIO_CORTE = 2022  # entrenamiento hasta este anio incluido; prueba, posteriores

# --- Variables de PERFIL: se conocen antes de que la atleta compita ---
PERFIL_NUM = [
    "peso_corporal_kg", "edad", "anio", "n_competicion",
    "pib_per_capita_ppa", "idh", "indice_desigualdad_gen",
    "tasa_actividad_femenina", "esperanza_vida_femenina",
]
PERFIL_CAT = [
    "equipamiento", "tipo_equipamiento", "ambito_federacion",
    "control_antidoping", "region", "iso3",
]

# --- Variables de HISTORIAL: marcas previas de la propia atleta ---
HISTORIAL_NUM = [
    "total_anterior", "mejor_total_previo", "dias_desde_anterior",
    "total_competiciones_atleta", "anios_trayectoria",
]

# --- PROHIBIDAS: contienen la respuesta o se miden durante el evento ---
# Se listan de forma explicita para poder auditar que no se cuela ninguna.
FUGA = {
    # Componentes del total: su suma ES el objetivo
    "kg_sentadilla", "kg_banca", "kg_peso_muerto",
    "pct_sentadilla", "pct_banca", "pct_peso_muerto",
    "rel_sentadilla", "rel_banca", "rel_peso_muerto",
    "ratio_banca_sentadilla", "ratio_muerto_sentadilla", "perfil_fuerza",
    # Indices calculados a partir del total
    "puntos_dots", "puntos_wilks", "puntos_goodlift", "fuerza_relativa",
    "brecha_total_pct", "brecha_fuerza_rel_pct", "fuerza_rel_p50_m",
    # Derivadas que usan el total del propio evento
    "mejora_kg", "mejora_pct", "es_record_personal",
    # Medidas tomadas durante la competicion a predecir
    "posicion", "es_podio", "es_primera",
    "intentos_registrados", "intentos_validos", "tasa_acierto_intentos",
    "tiene_detalle_intentos",
    # Identificadores y texto libre
    "id_atleta", "nombre_atleta", "nombre_competicion", "ciudad_competicion",
    "region_competicion", "federacion", "federacion_matriz", "division",
    "categoria_peso_oficial", "fecha",
}

ETIQUETAS = {
    "peso_corporal_kg": "Peso corporal", "edad": "Edad", "anio": "Año",
    "n_competicion": "Nº de competición", "equipamiento": "Equipamiento",
    "tipo_equipamiento": "Modalidad (con/sin equipo)",
    "ambito_federacion": "Ámbito federativo",
    "control_antidoping": "Control antidopaje declarado",
    "region": "Región", "iso3": "País",
    "pib_per_capita_ppa": "PIB per cápita del país",
    "idh": "IDH del país", "indice_desigualdad_gen": "Desigualdad de género",
    "tasa_actividad_femenina": "Actividad laboral femenina",
    "esperanza_vida_femenina": "Esperanza de vida femenina",
    "total_anterior": "Total en la competición anterior",
    "mejor_total_previo": "Mejor total previo",
    "dias_desde_anterior": "Días desde la anterior",
    "total_competiciones_atleta": "Competiciones totales de la atleta",
    "anios_trayectoria": "Años de trayectoria",
}


def _sep(titulo: str) -> None:
    print("\n" + "=" * 74)
    print(titulo)
    print("=" * 74)


# ===========================================================================
# PREPARACION
# ===========================================================================
def preparar() -> tuple[pd.DataFrame, pd.DataFrame]:
    _sep("PREPARACION DE LOS DATOS")

    ruta = cfg.DATASET_FINAL_PLANO if cfg.DATASET_FINAL_PLANO.exists() else cfg.DATASET_FINAL
    usar = list(dict.fromkeys(PERFIL_NUM + PERFIL_CAT + HISTORIAL_NUM
                              + [OBJETIVO, "es_debut"]))
    df = pd.read_csv(ruta, low_memory=False, usecols=usar)
    print(f"  Cargadas {len(df):,} filas y {df.shape[1]} columnas de {ruta.name}")

    # Auditoria de fuga: ninguna variable prohibida puede estar entre las
    # predictoras. Se comprueba en codigo, no de memoria.
    predictoras = set(PERFIL_NUM + PERFIL_CAT + HISTORIAL_NUM)
    colision = predictoras & FUGA
    assert not colision, f"FUGA DE DATOS detectada: {colision}"
    print(f"  Auditoria de fuga: OK ({len(predictoras)} predictoras, "
          f"{len(FUGA)} variables excluidas por diseño)")

    df = df[df[OBJETIVO].notna()].copy()
    for c in PERFIL_CAT:
        df[c] = df[c].astype("category")

    entrena = df[df["anio"] <= ANIO_CORTE]
    prueba = df[df["anio"] > ANIO_CORTE]
    print(f"\n  Reparto TEMPORAL (no aleatorio):")
    print(f"    Entrenamiento  hasta {ANIO_CORTE}: {len(entrena):>8,} filas "
          f"({len(entrena) / len(df) * 100:.1f}%)")
    print(f"    Prueba        {ANIO_CORTE + 1}-2026: {len(prueba):>8,} filas "
          f"({len(prueba) / len(df) * 100:.1f}%)")
    print(f"    Total {OBJETIVO}: media entrenamiento {entrena[OBJETIVO].mean():.1f} kg, "
          f"media prueba {prueba[OBJETIVO].mean():.1f} kg")

    RES["preparacion"] = {
        "n_total": int(len(df)), "n_entrenamiento": int(len(entrena)),
        "n_prueba": int(len(prueba)), "anio_corte": ANIO_CORTE,
        "n_predictoras_perfil": len(PERFIL_NUM + PERFIL_CAT),
        "n_predictoras_historial": len(HISTORIAL_NUM),
        "n_excluidas_por_fuga": len(FUGA),
        "media_objetivo_entrenamiento": round(float(entrena[OBJETIVO].mean()), 2),
        "media_objetivo_prueba": round(float(prueba[OBJETIVO].mean()), 2)}
    return entrena, prueba


def _evaluar(nombre: str, y_real, y_pred, segundos: float) -> dict:
    mae = mean_absolute_error(y_real, y_pred)
    rmse = root_mean_squared_error(y_real, y_pred)
    r2 = r2_score(y_real, y_pred)
    # Error porcentual absoluto medio: mas facil de comunicar que el MAE en kg
    mape = np.mean(np.abs((y_real - y_pred) / y_real)) * 100
    print(f"  {nombre:<26} MAE {mae:>6.2f} kg | RMSE {rmse:>6.2f} kg | "
          f"R2 {r2:>6.3f} | error {mape:>5.2f}% | {segundos:>5.1f}s")
    return {"modelo": nombre, "mae_kg": round(float(mae), 3),
            "rmse_kg": round(float(rmse), 3), "r2": round(float(r2), 4),
            "error_pct": round(float(mape), 3), "segundos": round(segundos, 1)}


# ===========================================================================
# ENTRENAMIENTO Y COMPARACION
# ===========================================================================
def entrenar(entrena: pd.DataFrame, prueba: pd.DataFrame) -> dict:
    _sep("ENTRENAMIENTO Y COMPARACION DE MODELOS")

    perfil = PERFIL_NUM + PERFIL_CAT
    Xe, ye = entrena[perfil], entrena[OBJETIVO]
    Xp, yp = prueba[perfil], prueba[OBJETIVO]

    print(f"\n  Evaluacion sobre TODO el conjunto de prueba ({len(prueba):,} filas)")
    print("  " + "-" * 70)
    resultados = []

    # --- 1. Base: predecir siempre la media del entrenamiento --------------
    t = time.perf_counter()
    base = DummyRegressor(strategy="mean").fit(Xe, ye)
    resultados.append(_evaluar("1. Base (media)", yp, base.predict(Xp),
                               time.perf_counter() - t))

    # --- 2. Lineal: Ridge con codificacion one-hot -------------------------
    t = time.perf_counter()
    lineal = Pipeline([
        ("prep", ColumnTransformer([
            ("num", StandardScaler(), PERFIL_NUM),
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50),
             PERFIL_CAT)])),
        ("mod", Ridge(alpha=1.0)),
    ])
    # Ridge no admite ausentes: se imputan por la mediana del entrenamiento
    medianas = Xe[PERFIL_NUM].median()
    lineal.fit(Xe.fillna(medianas), ye)
    resultados.append(_evaluar("2. Lineal (Ridge)", yp,
                               lineal.predict(Xp.fillna(medianas)),
                               time.perf_counter() - t))

    # --- 3. Perfil: Gradient Boosting --------------------------------------
    t = time.perf_counter()
    gb_perfil = HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.08, max_depth=None, max_leaf_nodes=48,
        min_samples_leaf=40, l2_regularization=1.0,
        categorical_features="from_dtype", early_stopping=True,
        validation_fraction=0.12, n_iter_no_change=25,
        random_state=cfg.SEMILLA)
    gb_perfil.fit(Xe, ye)
    pred_perfil = gb_perfil.predict(Xp)
    resultados.append(_evaluar("3. Perfil (Gradient Boost)", yp, pred_perfil,
                               time.perf_counter() - t))
    print(f"     -> arboles construidos: {gb_perfil.n_iter_} "
          f"(parada temprana activada)")

    # --- 4. Historial: comparacion justa en el mismo subconjunto -----------
    # El modelo con historial solo puede predecir cuando existe una marca
    # anterior. Para que la comparacion sea honesta, ambos modelos se evaluan
    # sobre las mismas filas: las de atletas que ya habian competido.
    print(f"\n  Comparacion JUSTA solo en filas con historial disponible")
    print("  " + "-" * 70)
    e_h = entrena[entrena["total_anterior"].notna()]
    p_h = prueba[prueba["total_anterior"].notna()]
    print(f"  Entrenamiento {len(e_h):,} filas | prueba {len(p_h):,} filas "
          f"({len(p_h) / len(prueba) * 100:.1f}% del total: el resto son debuts)")

    completo = perfil + HISTORIAL_NUM
    resultados.append(_evaluar("3b. Perfil (mismas filas)", p_h[OBJETIVO],
                               gb_perfil.predict(p_h[perfil]), 0.0))

    t = time.perf_counter()
    gb_hist = HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.08, max_depth=None, max_leaf_nodes=48,
        min_samples_leaf=40, l2_regularization=1.0,
        categorical_features="from_dtype", early_stopping=True,
        validation_fraction=0.12, n_iter_no_change=25,
        random_state=cfg.SEMILLA)
    gb_hist.fit(e_h[completo], e_h[OBJETIVO])
    pred_hist = gb_hist.predict(p_h[completo])
    res_hist = _evaluar("4. Perfil + historial", p_h[OBJETIVO], pred_hist,
                        time.perf_counter() - t)
    resultados.append(res_hist)

    # Cuanto aporta conocer la trayectoria
    mae_sin = resultados[-2]["mae_kg"]
    mejora = (mae_sin - res_hist["mae_kg"]) / mae_sin * 100
    print(f"\n  APORTACION DEL HISTORIAL: el error baja de {mae_sin:.2f} kg a "
          f"{res_hist['mae_kg']:.2f} kg ({mejora:.1f}% menos)")
    RES["aportacion_historial_pct"] = round(float(mejora), 2)
    RES["comparacion_modelos"] = resultados

    return {"gb_perfil": gb_perfil, "gb_hist": gb_hist, "lineal": lineal,
            "prueba_perfil": (Xp, yp, pred_perfil),
            "prueba_hist": (p_h[completo], p_h[OBJETIVO], pred_hist),
            "columnas_completo": completo}


# ===========================================================================
# EXPLICABILIDAD
# ===========================================================================
def explicar(modelos: dict) -> pd.DataFrame:
    _sep("EXPLICABILIDAD: QUE DETERMINA EL RENDIMIENTO")

    # Importancia por PERMUTACION: se mide cuanto empeora el modelo al
    # desordenar cada variable. Es preferible a la importancia interna del
    # arbol, que premia artificialmente a las variables de alta cardinalidad
    # (como el pais, con 114 categorias).
    X, y, _ = modelos["prueba_hist"]
    n = min(25_000, len(X))
    Xm = X.sample(n, random_state=cfg.SEMILLA)
    ym = y.loc[Xm.index]
    print(f"  Importancia por permutacion sobre {n:,} filas de prueba "
          f"(5 repeticiones)...")

    imp = permutation_importance(
        modelos["gb_hist"], Xm, ym, n_repeats=5,
        random_state=cfg.SEMILLA, scoring="neg_mean_absolute_error", n_jobs=1)

    tabla = (pd.DataFrame({
        "variable": Xm.columns,
        "importancia_kg": imp.importances_mean,
        "desviacion": imp.importances_std})
        .assign(etiqueta=lambda d: d["variable"].map(ETIQUETAS).fillna(d["variable"]))
        .sort_values("importancia_kg", ascending=False)
        .reset_index(drop=True))
    tabla["pct_del_total"] = (tabla["importancia_kg"]
                              / tabla["importancia_kg"].clip(lower=0).sum() * 100).round(1)

    print(f"\n  {'Variable':<38}{'Impacto (kg)':>14}{'% del total':>13}")
    for _, f in tabla.head(14).iterrows():
        print(f"  {f['etiqueta']:<38}{f['importancia_kg']:>14.3f}"
              f"{f['pct_del_total']:>12.1f}%")

    RES["importancia_variables"] = tabla.round(4).to_dict("records")
    tabla.to_csv(cfg.REPORTS / "importancia_variables.csv", index=False,
                 encoding="utf-8")
    print(f"\n  -> reports/importancia_variables.csv")
    return tabla


# ===========================================================================
# DIAGNOSTICO DEL MODELO
# ===========================================================================
def diagnosticar(modelos: dict) -> None:
    _sep("DIAGNOSTICO: DONDE ACIERTA Y DONDE FALLA EL MODELO")

    X, y, pred = modelos["prueba_hist"]
    res = y - pred
    print(f"  Residuo medio      : {res.mean():+.3f} kg  "
          f"(cercano a 0 = sin sesgo sistematico)")
    print(f"  Desviacion tipica  : {res.std():.2f} kg")
    print(f"  Residuo mediano    : {res.median():+.3f} kg")
    print(f"  Dentro de +-10 kg  : {(res.abs() <= 10).mean() * 100:.1f}% de los casos")
    print(f"  Dentro de +-20 kg  : {(res.abs() <= 20).mean() * 100:.1f}% de los casos")

    RES["diagnostico"] = {
        "residuo_medio": round(float(res.mean()), 4),
        "residuo_std": round(float(res.std()), 3),
        "residuo_mediano": round(float(res.median()), 4),
        "pct_dentro_10kg": round(float((res.abs() <= 10).mean() * 100), 2),
        "pct_dentro_20kg": round(float((res.abs() <= 20).mean() * 100), 2)}

    # Error por tramo de marca: revela si el modelo falla mas en los extremos
    tramos = pd.cut(y, bins=[0, 200, 300, 400, 500, 1000],
                    labels=["<200 kg", "200-300", "300-400", "400-500", ">500 kg"])
    porTramo = (pd.DataFrame({"real": y, "pred": pred, "tramo": tramos})
                .groupby("tramo", observed=True)
                .apply(lambda g: pd.Series({
                    "n": len(g),
                    "mae": mean_absolute_error(g["real"], g["pred"]),
                    "sesgo": (g["pred"] - g["real"]).mean()}),
                    include_groups=False).round(2))
    print(f"\n  ERROR POR TRAMO DE MARCA:")
    print(porTramo.to_string())
    RES["error_por_tramo"] = porTramo.to_dict("index")


# ===========================================================================
# FIGURAS
# ===========================================================================
def figuras(modelos: dict, importancia: pd.DataFrame) -> None:
    _sep("FIGURAS DEL MODELADO")

    comp = pd.DataFrame(RES["comparacion_modelos"])

    # --- Figura 1: comparacion de modelos ---------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    c = comp[~comp["modelo"].str.startswith("3b")]
    colores = [estilo.GRIS, estilo.AZUL, estilo.MORADO, estilo.MAGENTA]
    barras = ax1.bar(range(len(c)), c["mae_kg"], color=colores[:len(c)], alpha=0.9)
    ax1.set_xticks(range(len(c)))
    ax1.set_xticklabels([m.split(". ", 1)[-1] for m in c["modelo"]],
                        rotation=18, ha="right", fontsize=9.5)
    for b, v in zip(barras, c["mae_kg"]):
        ax1.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.1f}",
                 ha="center", fontsize=10, fontweight="bold")
    estilo.titular(ax1, "Error de predicción por modelo",
                   "Error absoluto medio en kg, más bajo es mejor")
    ax1.set_ylabel("MAE (kg)")

    barras2 = ax2.bar(range(len(c)), c["r2"], color=colores[:len(c)], alpha=0.9)
    ax2.set_xticks(range(len(c)))
    ax2.set_xticklabels([m.split(". ", 1)[-1] for m in c["modelo"]],
                        rotation=18, ha="right", fontsize=9.5)
    for b, v in zip(barras2, c["r2"]):
        ax2.text(b.get_x() + b.get_width() / 2, max(v, 0) + 0.02, f"{v:.3f}",
                 ha="center", fontsize=10, fontweight="bold")
    estilo.titular(ax2, "Varianza explicada (R²)",
                   "Proporción de la variabilidad del total que capta el modelo")
    ax2.set_ylabel("R²")
    ax2.set_ylim(0, 1.05)
    estilo.pie_de_fuente(fig, "Validación temporal: entrenamiento hasta 2022, "
                              "prueba 2023-2026")
    estilo.guardar(fig, "m1_comparacion_modelos")
    print("  [figura] m1_comparacion_modelos.png")

    # --- Figura 2: importancia de variables --------------------------------
    top = importancia.head(13).iloc[::-1]
    fig, ax = plt.subplots(figsize=(11.5, 7))
    ax.barh(top["etiqueta"], top["importancia_kg"],
            xerr=top["desviacion"], color=estilo.MORADO, alpha=0.9,
            error_kw={"ecolor": estilo.GRIS, "capsize": 3, "lw": 1})
    estilo.titular(ax, "Qué determina realmente la marca de una atleta",
                   "Aumento del error (kg) al desordenar cada variable. "
                   "importancia por permutación")
    ax.set_xlabel("Impacto en el error (kg)")
    ax.grid(axis="x", alpha=0.6)
    ax.grid(axis="y", visible=False)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "m2_importancia_variables")
    print("  [figura] m2_importancia_variables.png")

    # --- Figura 3: predicho vs real y residuos ----------------------------
    X, y, pred = modelos["prueba_hist"]
    m = min(30_000, len(y))
    idx = pd.Series(y.index).sample(m, random_state=cfg.SEMILLA)
    yr, yp_ = y.loc[idx], pd.Series(pred, index=y.index).loc[idx]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    ax1.scatter(yr, yp_, s=4, alpha=0.10, color=estilo.MORADO, edgecolors="none")
    lim = [min(yr.min(), yp_.min()) - 10, max(yr.max(), yp_.max()) + 10]
    ax1.plot(lim, lim, color=estilo.MAGENTA, ls="--", lw=2,
             label="Predicción perfecta")
    ax1.set_xlim(lim)
    ax1.set_ylim(lim)
    r2 = r2_score(y, pred)
    estilo.titular(ax1, "Marca predicha frente a marca real",
                   f"Conjunto de prueba 2023-2026 · R² = {r2:.3f}")
    ax1.set_xlabel("Total real (kg)")
    ax1.set_ylabel("Total predicho (kg)")
    ax1.legend()

    res = y - pred
    ax2.hist(res, bins=90, color=estilo.TEAL, alpha=0.85, edgecolor="white",
             linewidth=0.4)
    ax2.axvline(0, color=estilo.MAGENTA, ls="--", lw=2)
    ax2.axvline(res.mean(), color=estilo.TINTA, ls=":", lw=2,
                label=f"Media: {res.mean():+.2f} kg")
    estilo.titular(ax2, "Distribución del error",
                   f"Centrada y simétrica: sin sesgo sistemático · "
                   f"{(res.abs() <= 20).mean() * 100:.0f}% dentro de ±20 kg")
    ax2.set_xlabel("Error real − predicho (kg)")
    ax2.set_ylabel("Nº de casos")
    ax2.set_xlim(-120, 120)
    ax2.legend()
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "m3_diagnostico_modelo")
    print("  [figura] m3_diagnostico_modelo.png")


def main() -> None:
    entrena, prueba = preparar()
    modelos = entrenar(entrena, prueba)
    importancia = explicar(modelos)
    diagnosticar(modelos)
    figuras(modelos, importancia)

    destino = cfg.REPORTS / "resultados_modelos.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(RES, f, ensure_ascii=False, indent=2, default=str)
    _sep("MODELADO COMPLETADO")
    print(f"  Resultados: {destino.relative_to(cfg.RAIZ)}")


if __name__ == "__main__":
    main()
