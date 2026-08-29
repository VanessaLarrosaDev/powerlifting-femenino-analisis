"""
Analisis del conjunto final, combinando estadistica descriptiva, inferencial y
visualizacion. Cada bloque responde a una cuestion concreta: la evolucion de la
participacion, su reparto geografico, la relacion con la igualdad de genero y el
desarrollo del pais, el escalado de la fuerza con el peso corporal, la edad de
maximo rendimiento, los arquetipos de fuerza, el efecto del equipamiento, la
progresion a lo largo de la trayectoria, la brecha respecto a los hombres y la
declaracion de control antidopaje.

Las figuras se guardan en reports/figures/ y los resultados numericos en
reports/resultados_analisis.json, que alimenta el informe.

Ejecucion:  python src/analisis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
import estilo

estilo.aplicar()
RES: dict = {}


def _sep(titulo: str) -> None:
    print("\n" + "=" * 74)
    print(titulo)
    print("=" * 74)


def cargar() -> pd.DataFrame:
    _sep("CARGA DEL CONJUNTO FINAL")
    ruta = cfg.DATASET_FINAL_PLANO if cfg.DATASET_FINAL_PLANO.exists() else cfg.DATASET_FINAL
    df = pd.read_csv(ruta, low_memory=False, parse_dates=["fecha"])
    print(f"  {df.shape[0]:,} filas x {df.shape[1]} columnas   ({ruta.name})")
    return df


# ===========================================================================
# A1. PANORAMA GENERAL
# ===========================================================================
def a1_panorama(df: pd.DataFrame) -> None:
    _sep("A1. PANORAMA GENERAL")

    RES["panorama"] = {
        "n_registros": int(len(df)),
        "n_atletas": int(df["id_atleta"].nunique()),
        "n_paises": int(df["iso3"].nunique()),
        "n_federaciones": int(df["federacion"].nunique()),
        "n_competiciones": int(df["nombre_competicion"].nunique()),
        "periodo": [str(df["fecha"].min().date()), str(df["fecha"].max().date())],
        "competiciones_por_atleta": round(float(df.groupby("id_atleta").size().mean()), 2),
    }
    for k, v in RES["panorama"].items():
        print(f"  {k:<28} {v}")

    print("\n  Descriptivos de las variables de rendimiento:")
    desc = df[["total_kg", "peso_corporal_kg", "fuerza_relativa", "puntos_dots",
               "kg_sentadilla", "kg_banca", "kg_peso_muerto", "edad"]].describe()
    desc = desc.T[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].round(2)
    print(desc.to_string())
    RES["descriptivos"] = desc.to_dict("index")

    # Asimetria y curtosis: justifica el uso de medianas y de pruebas robustas
    print("\n  Forma de las distribuciones:")
    for c in ["total_kg", "fuerza_relativa", "puntos_dots"]:
        s = df[c].dropna()
        asim, curt = stats.skew(s), stats.kurtosis(s)
        print(f"    {c:<18} asimetria={asim:+.3f}  curtosis={curt:+.3f}")
        RES.setdefault("forma_distribuciones", {})[c] = {
            "asimetria": round(float(asim), 3), "curtosis": round(float(curt), 3)}

    # Figura: distribuciones principales
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, (col, etiq) in zip(axes, [
            ("total_kg", "Total levantado (kg)"),
            ("fuerza_relativa", "Fuerza relativa (total / peso corporal)"),
            ("puntos_dots", "Puntos DOTS (rendimiento normalizado)")]):
        ax.hist(df[col].dropna(), bins=70, color=estilo.MORADO, alpha=0.85,
                edgecolor="white", linewidth=0.4)
        ax.axvline(df[col].median(), color=estilo.MAGENTA, ls="--", lw=2,
                   label=f"Mediana: {df[col].median():.1f}")
        ax.set_xlabel(etiq)
        ax.set_ylabel("Nº de registros")
        ax.legend()
    fig.suptitle("Distribución de las variables de rendimiento del powerlifting femenino",
                 fontsize=14, fontweight="bold", x=0.01, ha="left", y=1.04)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a1_distribuciones_rendimiento")
    print("\n  [figura] a1_distribuciones_rendimiento.png")


# ===========================================================================
# A2. EVOLUCION TEMPORAL DE LA PARTICIPACION
# ===========================================================================
def a2_evolucion(df: pd.DataFrame) -> None:
    _sep("A2. EVOLUCION TEMPORAL DE LA PARTICIPACION FEMENINA")

    porano = (df.groupby("anio")
                .agg(registros=("total_kg", "size"),
                     atletas=("id_atleta", "nunique"),
                     total_mediano=("total_kg", "median"),
                     dots_mediano=("puntos_dots", "median"))
                .reset_index())
    porano = porano[porano["anio"] <= 2025]  # 2026 esta incompleto

    # La cuota femenina se toma del agregado original, no del conjunto final
    # (ver la nota metodologica mas abajo).
    _p = pd.read_csv(cfg.EXTERNAL / "participacion_por_pais_anio.csv")
    _c = (_p.groupby("anio")
            .agg(m=("n_mujeres_pais_anio", "sum"), h=("n_hombres_pais_anio", "sum")))
    _c["pct_femenina"] = (_c["m"] / (_c["m"] + _c["h"]) * 100).round(2)
    porano = porano.merge(_c[["pct_femenina"]], on="anio", how="left")

    print(porano.tail(15).to_string(index=False))
    RES["evolucion_anual"] = porano.round(2).to_dict("records")

    # Tasa de crecimiento anual compuesta de la participacion (2000-2025)
    p = porano[porano["anio"].between(2000, 2025)]
    n0, n1 = p["atletas"].iloc[0], p["atletas"].iloc[-1]
    anios = p["anio"].iloc[-1] - p["anio"].iloc[0]
    tcac = ((n1 / n0) ** (1 / anios) - 1) * 100
    print(f"\n  Atletas unicas 2000: {n0:,}   2025: {n1:,}")
    print(f"  Crecimiento total: x{n1 / n0:.1f}   TCAC {anios} anios: {tcac:.2f}% anual")
    RES["crecimiento"] = {"atletas_2000": int(n0), "atletas_2025": int(n1),
                          "multiplicador": round(float(n1 / n0), 2),
                          "tcac_pct": round(float(tcac), 2)}

    # Tendencia del peso relativo de las mujeres en el deporte.
    #
    # La cuota se calcula como mujeres / (mujeres + hombres) sobre el agregado
    # original, y NO promediando la columna pct_participacion_femenina sobre las
    # filas del conjunto final. Ese promedio estaria sesgado al alza, porque
    # cada fila es una participacion femenina y por tanto los paises-anio con
    # mas mujeres pesarian mas en la media. Ademas, las competiciones
    # exclusivamente femeninas (cuota del 100%) distorsionan cualquier media
    # simple entre paises.
    part = pd.read_csv(cfg.EXTERNAL / "participacion_por_pais_anio.csv")
    part = part[part["anio"].between(2000, 2025)]
    agr = part.groupby("anio").agg(m=("n_mujeres_pais_anio", "sum"),
                                   h=("n_hombres_pais_anio", "sum"))
    pf = (agr["m"] / (agr["m"] + agr["h"]) * 100).rename("cuota_femenina")
    reg = stats.linregress(pf.index, pf.values)
    print(f"  Cuota femenina 2000: {pf.iloc[0]:.1f}%   2025: {pf.iloc[-1]:.1f}%")
    print(f"  Tendencia: {reg.slope:+.3f} puntos porcentuales/anio "
          f"(R2={reg.rvalue ** 2:.3f}, p={reg.pvalue:.2e})")
    RES["tendencia_cuota_femenina"] = {
        "cuota_2000": round(float(pf.iloc[0]), 2), "cuota_2025": round(float(pf.iloc[-1]), 2),
        "pendiente_pp_anio": round(float(reg.slope), 4),
        "r2": round(float(reg.rvalue ** 2), 4), "p_valor": float(reg.pvalue)}

    # Figura de doble panel
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8.5), sharex=True,
                                   height_ratios=[1.3, 1])
    ax1.fill_between(porano["anio"], porano["atletas"], color=estilo.MORADO, alpha=0.22)
    ax1.plot(porano["anio"], porano["atletas"], color=estilo.MORADO, lw=2.6)
    estilo.titular(ax1, "Atletas femeninas únicas en competición cada año",
                   f"De {n0:,} en 2000 a {n1:,} en 2025: crecimiento de "
                   f"{tcac:.1f}% anual compuesto")
    ax1.set_ylabel("Atletas únicas")

    ax2.plot(pf.index, pf.values, color=estilo.MAGENTA, lw=2.6, marker="o", ms=4)
    ax2.plot(pf.index, reg.intercept + reg.slope * pf.index, color=estilo.GRIS,
             ls="--", lw=1.6,
             label=f"Tendencia: {reg.slope:+.2f} p.p./año (R²={reg.rvalue ** 2:.2f})")
    estilo.titular(ax2, "Cuota femenina sobre el total de participaciones",
                   "Porcentaje de mujeres entre todas las personas que compiten")
    ax2.set_ylabel("% de mujeres")
    ax2.set_xlabel("Año")
    ax2.legend()
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a2_evolucion_participacion")
    print("  [figura] a2_evolucion_participacion.png")


# ===========================================================================
# A3. DISTRIBUCION GEOGRAFICA
# ===========================================================================
def a3_geografia(df: pd.DataFrame) -> None:
    _sep("A3. DISTRIBUCION GEOGRAFICA")

    porpais = (df.groupby(["iso3", "pais_competicion", "region"])
                 .agg(registros=("total_kg", "size"),
                      atletas=("id_atleta", "nunique"),
                      total_mediano=("total_kg", "median"),
                      dots_mediano=("puntos_dots", "median"),
                      cuota_femenina=("pct_participacion_femenina", "mean"),
                      gii=("indice_desigualdad_gen", "mean"),
                      idh=("idh", "mean"))
                 .reset_index()
                 .sort_values("atletas", ascending=False))
    print("  TOP 15 PAISES POR NUMERO DE ATLETAS:")
    print(porpais.head(15)[["pais_competicion", "region", "atletas",
                            "total_mediano", "dots_mediano", "cuota_femenina"]]
          .to_string(index=False))
    RES["top_paises"] = porpais.head(25).round(3).to_dict("records")

    concentracion = porpais["atletas"].head(5).sum() / porpais["atletas"].sum() * 100
    print(f"\n  Concentracion: los 5 primeros paises reunen el {concentracion:.1f}% "
          f"de las atletas")
    RES["concentracion_top5_pct"] = round(float(concentracion), 2)

    porregion = (df.groupby("region")
                   .agg(atletas=("id_atleta", "nunique"),
                        registros=("total_kg", "size"),
                        dots_mediano=("puntos_dots", "median"),
                        cuota_femenina=("pct_participacion_femenina", "mean"))
                   .sort_values("atletas", ascending=False))
    print("\n  POR REGION:")
    print(porregion.round(2).to_string())
    RES["por_region"] = porregion.round(2).to_dict("index")

    # Figura: top paises + cuota femenina por region
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6),
                                   gridspec_kw={"width_ratios": [1.2, 1]})
    top = porpais.head(15).sort_values("atletas")
    ax1.barh(top["pais_competicion"], top["atletas"], color=estilo.MORADO, alpha=0.9)
    estilo.titular(ax1, "Países con más atletas femeninas",
                   "Atletas únicas registradas en competición, 1975-2026")
    ax1.set_xlabel("Atletas únicas")
    ax1.grid(axis="x", alpha=0.6)
    ax1.grid(axis="y", visible=False)

    r = porregion.sort_values("cuota_femenina")
    ax2.barh(r.index, r["cuota_femenina"], color=estilo.MAGENTA, alpha=0.9)
    estilo.titular(ax2, "Cuota femenina media por región",
                   "% de mujeres sobre el total de participaciones")
    ax2.set_xlabel("% de mujeres")
    ax2.grid(axis="x", alpha=0.6)
    ax2.grid(axis="y", visible=False)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a3_geografia")
    print("  [figura] a3_geografia.png")


# ===========================================================================
# A4. PREGUNTA CENTRAL: PARTICIPACION FEMENINA E IGUALDAD DE GENERO
# ===========================================================================
def a4_igualdad(df: pd.DataFrame) -> None:
    _sep("A4. PREGUNTA CENTRAL | PARTICIPACION FEMENINA vs IGUALDAD DE GENERO")

    # El analisis se hace a nivel pais-anio, no a nivel atleta: la unidad de
    # observacion correcta para relacionar contexto nacional con participacion.
    # Se exige un minimo de 40 registros para que la cuota sea estable y se
    # usan solo anios con indicador observado (no propagado).
    pa = (df[~df["indicadores_imputados"]]
          .groupby(["iso3", "pais_competicion", "anio"])
          .agg(registros=("total_kg", "size"),
               cuota_femenina=("pct_participacion_femenina", "first"),
               gii=("indice_desigualdad_gen", "first"),
               idh=("idh", "first"),
               gdi=("indice_desarrollo_gen", "first"),
               pib=("pib_per_capita_ppa", "first"),
               actividad_fem=("tasa_actividad_femenina", "first"),
               educacion_fem=("matricula_superior_femenina", "first"),
               dots_mediano=("puntos_dots", "median"))
          .reset_index())
    pa = pa[pa["registros"] >= 40].dropna(subset=["cuota_femenina"])
    print(f"  Unidad de analisis: pais-anio con >=40 registros y dato observado")
    print(f"  Observaciones: {len(pa):,}  ({pa['iso3'].nunique()} paises, "
          f"{pa['anio'].min()}-{pa['anio'].max()})")

    print("\n  CORRELACION con la cuota de participacion femenina:")
    print(f"  {'Indicador':<34}{'Pearson':>10}{'p-valor':>12}"
          f"{'Spearman':>11}{'p-valor':>12}{'n':>8}")
    correl = {}
    for col, etiq in [("gii", "Indice desigualdad genero (GII)"),
                      ("idh", "Indice desarrollo humano (IDH)"),
                      ("gdi", "Indice desarrollo genero (GDI)"),
                      ("pib", "PIB per capita (PPA)"),
                      ("actividad_fem", "Tasa actividad laboral femenina"),
                      ("educacion_fem", "Matriculacion superior femenina")]:
        sub = pa[["cuota_femenina", col]].dropna()
        if len(sub) < 30:
            continue
        rp, pp = stats.pearsonr(sub[col], sub["cuota_femenina"])
        rs, ps = stats.spearmanr(sub[col], sub["cuota_femenina"])
        print(f"  {etiq:<34}{rp:>+10.3f}{pp:>12.2e}{rs:>+11.3f}{ps:>12.2e}{len(sub):>8,}")
        correl[col] = {"etiqueta": etiq, "pearson": round(float(rp), 4),
                       "p_pearson": float(pp), "spearman": round(float(rs), 4),
                       "p_spearman": float(ps), "n": int(len(sub))}
    RES["correlaciones_igualdad"] = correl

    # Comparacion de grupos: paises con muy baja vs alta desigualdad
    grupos = (df[~df["indicadores_imputados"]]
              .dropna(subset=["grupo_desigualdad"])
              .groupby(["grupo_desigualdad", "iso3", "anio"], observed=True)
              ["pct_participacion_femenina"].first().reset_index())
    resumen = grupos.groupby("grupo_desigualdad", observed=True)[
        "pct_participacion_femenina"].agg(["count", "mean", "median", "std"]).round(2)
    print("\n  CUOTA FEMENINA POR NIVEL DE DESIGUALDAD DEL PAIS:")
    print(resumen.to_string())
    RES["cuota_por_grupo_desigualdad"] = resumen.to_dict("index")

    # ANOVA + Kruskal-Wallis (no parametrica, robusta a no-normalidad)
    muestras = [g["pct_participacion_femenina"].dropna().values
                for _, g in grupos.groupby("grupo_desigualdad", observed=True)]
    muestras = [m for m in muestras if len(m) >= 10]
    if len(muestras) >= 2:
        f, pf = stats.f_oneway(*muestras)
        h, ph = stats.kruskal(*muestras)
        print(f"\n  ANOVA           F={f:.2f}  p={pf:.3e}")
        print(f"  Kruskal-Wallis  H={h:.2f}  p={ph:.3e}")
        RES["prueba_grupos_desigualdad"] = {
            "anova_F": round(float(f), 3), "anova_p": float(pf),
            "kruskal_H": round(float(h), 3), "kruskal_p": float(ph),
            "n_grupos": len(muestras)}

    # -----------------------------------------------------------------------
    # CONTROL DEL EFECTO TEMPORAL
    # -----------------------------------------------------------------------
    # Las correlaciones anteriores son enganosas: la cuota femenina crece con
    # el tiempo en TODOS los paises (+0,9 p.p./anio, ver A2) y a la vez el
    # desarrollo humano crece y la desigualdad baja. El anio actua como
    # variable de confusion y puede invertir el signo de la relacion.
    # Se aborda de dos formas complementarias.
    print("\n  " + "-" * 68)
    print("  CONTROL DEL EFECTO TEMPORAL (el anio es variable de confusion)")
    print("  " + "-" * 68)

    # (a) Correlacion parcial: se elimina de ambas variables la parte
    #     explicada por el anio y se correlacionan los residuos.
    print("\n  (a) Correlacion PARCIAL controlando el anio:")
    parciales = {}
    for col, etiq in [("gii", "Desigualdad genero (GII)"),
                      ("idh", "Desarrollo humano (IDH)"),
                      ("pib", "PIB per capita (PPA)"),
                      ("educacion_fem", "Matriculacion superior fem.")]:
        sub = pa[["cuota_femenina", col, "anio"]].dropna()
        if len(sub) < 30:
            continue
        res_y = sub["cuota_femenina"] - np.polyval(
            np.polyfit(sub["anio"], sub["cuota_femenina"], 1), sub["anio"])
        res_x = sub[col] - np.polyval(
            np.polyfit(sub["anio"], sub[col], 1), sub["anio"])
        r, p = stats.pearsonr(res_x, res_y)
        cruda = stats.pearsonr(sub[col], sub["cuota_femenina"])[0]
        print(f"      {etiq:<30} cruda {cruda:+.3f}  ->  parcial {r:+.3f} "
              f"(p={p:.2e})")
        parciales[col] = {"etiqueta": etiq, "r_cruda": round(float(cruda), 4),
                          "r_parcial": round(float(r), 4), "p": float(p),
                          "n": int(len(sub))}
    RES["correlaciones_parciales"] = parciales

    # (b) Corte transversal reciente: un unico valor medio por pais en el
    #     periodo 2015-2022. Elimina por completo la dimension temporal y
    #     responde a "entre paises comparables hoy, importa la igualdad?".
    corte = (pa[pa["anio"].between(2015, 2022)]
             .groupby(["iso3", "pais_competicion"])
             .agg(cuota=("cuota_femenina", "mean"), gii=("gii", "mean"),
                  idh=("idh", "mean"), pib=("pib", "mean"),
                  educacion=("educacion_fem", "mean"),
                  registros=("registros", "sum"))
             .reset_index())
    corte = corte[corte["registros"] >= 200].dropna(subset=["cuota", "gii"])
    print(f"\n  (b) Corte transversal 2015-2022: {len(corte)} paises "
          f"con 200+ registros")
    transversal = {}
    for col, etiq in [("gii", "Desigualdad genero (GII)"),
                      ("idh", "Desarrollo humano (IDH)"),
                      ("pib", "PIB per capita (PPA)"),
                      ("educacion", "Matriculacion superior fem.")]:
        s = corte[["cuota", col]].dropna()
        if len(s) < 12:
            continue
        rp, pp = stats.pearsonr(s[col], s["cuota"])
        rs, ps = stats.spearmanr(s[col], s["cuota"])
        signif = "SIGNIFICATIVA" if pp < 0.05 else "no significativa"
        print(f"      {etiq:<30} r={rp:+.3f} (p={pp:.3f})  rho={rs:+.3f}  "
              f"n={len(s)}  {signif}")
        transversal[col] = {"etiqueta": etiq, "pearson": round(float(rp), 4),
                            "p": float(pp), "spearman": round(float(rs), 4),
                            "n": int(len(s))}
    RES["corte_transversal_2015_2022"] = transversal
    RES["paises_corte_transversal"] = corte.round(3).to_dict("records")

    # Diagnostico del sesgo de composicion: cuanto pesa Estados Unidos
    peso_usa = (df["iso3"] == "USA").mean() * 100
    print(f"\n  AVISO DE SESGO: Estados Unidos concentra el {peso_usa:.1f}% de los "
          f"registros.")
    print(f"  Cualquier correlacion global esta dominada por su trayectoria "
          f"interna, no por\n  la comparacion entre paises. De ahi que el corte "
          f"transversal sea la lectura valida.")
    RES["peso_usa_pct"] = round(float(peso_usa), 2)

    # Figura: dispersion GII vs cuota + boxplot por grupo
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6),
                                   gridspec_kw={"width_ratios": [1.35, 1]})
    # Panel 1: corte transversal por pais (sin el efecto temporal de confusion)
    rp, pp = stats.pearsonr(corte["gii"], corte["cuota"])
    reg = stats.linregress(corte["gii"], corte["cuota"])
    ax1.scatter(corte["gii"], corte["cuota"],
                s=np.clip(corte["registros"] / 120, 22, 420),
                c=corte["cuota"], cmap="magma_r", alpha=0.82,
                edgecolors="white", linewidths=0.8, zorder=3)
    xs = np.linspace(corte["gii"].min(), corte["gii"].max(), 50)
    ax1.plot(xs, reg.intercept + reg.slope * xs, color=estilo.TINTA, ls="--",
             lw=2, zorder=2,
             label=f"r = {rp:+.3f}  (p = {pp:.3f}, n = {len(corte)})")
    # Etiquetar los paises con mas volumen para dar contexto al lector
    for _, f in corte.nlargest(9, "registros").iterrows():
        ax1.annotate(f["pais_competicion"], (f["gii"], f["cuota"]),
                     textcoords="offset points", xytext=(7, 5), fontsize=8.5,
                     color=estilo.GRIS)
    veredicto = ("relación significativa" if pp < 0.05
                 else "sin relación estadísticamente significativa")
    estilo.titular(ax1, "Desigualdad de género y participación femenina, por país",
                   f"Media 2015-2022, países con 200+ registros; {veredicto}")
    ax1.set_xlabel("Índice de Desigualdad de Género (GII), donde 0 es igualdad plena")
    ax1.set_ylabel("% de mujeres en competición")
    ax1.legend(loc="upper right")

    datos_box = [g["pct_participacion_femenina"].dropna().values
                 for _, g in grupos.groupby("grupo_desigualdad", observed=True)]
    etiquetas = [str(k) for k, _ in grupos.groupby("grupo_desigualdad", observed=True)]
    bp = ax2.boxplot(datos_box, tick_labels=etiquetas, patch_artist=True,
                     medianprops={"color": estilo.TINTA, "lw": 2},
                     flierprops={"marker": ".", "markersize": 3,
                                 "alpha": 0.3, "markerfacecolor": estilo.GRIS})
    for caja, color in zip(bp["boxes"], [estilo.TEAL, estilo.MORADO_CLARO,
                                         estilo.MAGENTA, estilo.CORAL]):
        caja.set_facecolor(color)
        caja.set_alpha(0.75)
    estilo.titular(ax2, "Distribución de la cuota femenina",
                   "Agrupando los países por su nivel de desigualdad")
    ax2.set_ylabel("% de mujeres en competición")
    ax2.tick_params(axis="x", rotation=20)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a4_igualdad_participacion")
    print("  [figura] a4_igualdad_participacion.png")


# ===========================================================================
# A5. ESCALADO DE LA FUERZA CON EL PESO CORPORAL
# ===========================================================================
def a5_peso_fuerza(df: pd.DataFrame) -> None:
    _sep("A5. COMO ESCALA LA FUERZA CON EL PESO CORPORAL")

    d = df[["peso_corporal_kg", "total_kg", "fuerza_relativa", "categoria_peso",
            "tipo_equipamiento"]].dropna(subset=["peso_corporal_kg", "total_kg"])

    # Ley alometrica: Total = a * Peso^b. En log-log, b es la pendiente.
    # b < 1 implica retornos decrecientes: la fuerza crece menos que el peso.
    lx, ly = np.log(d["peso_corporal_kg"]), np.log(d["total_kg"])
    reg = stats.linregress(lx, ly)
    print(f"  Modelo alometrico  Total = a * Peso^b")
    print(f"    exponente b = {reg.slope:.4f}  (IC95%: "
          f"{reg.slope - 1.96 * reg.stderr:.4f} a {reg.slope + 1.96 * reg.stderr:.4f})")
    print(f"    R2 = {reg.rvalue ** 2:.4f}   p = {reg.pvalue:.2e}")
    print(f"    Interpretacion: al duplicar el peso corporal, el total se "
          f"multiplica por {2 ** reg.slope:.2f}")
    RES["alometria"] = {"exponente_b": round(float(reg.slope), 4),
                        "ic95": [round(float(reg.slope - 1.96 * reg.stderr), 4),
                                 round(float(reg.slope + 1.96 * reg.stderr), 4)],
                        "r2": round(float(reg.rvalue ** 2), 4),
                        "factor_al_duplicar_peso": round(float(2 ** reg.slope), 3)}

    porcat = (d.groupby("categoria_peso", observed=True)
                .agg(n=("total_kg", "size"), total_mediano=("total_kg", "median"),
                     fuerza_rel_mediana=("fuerza_relativa", "median"))
                .round(3))
    print("\n  POR CATEGORIA DE PESO:")
    print(porcat.to_string())
    RES["por_categoria_peso"] = porcat.to_dict("index")

    mejor = porcat["fuerza_rel_mediana"].idxmax()
    print(f"\n  Mayor fuerza relativa: categoria {mejor} "
          f"({porcat.loc[mejor, 'fuerza_rel_mediana']:.3f} x peso corporal)")
    RES["categoria_mas_eficiente"] = str(mejor)

    # Figura: nube con medianas por tramo de peso + fuerza relativa
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    m = d.sample(min(40_000, len(d)), random_state=cfg.SEMILLA)
    ax1.scatter(m["peso_corporal_kg"], m["total_kg"], s=4, alpha=0.10,
                color=estilo.MORADO, edgecolors="none")
    tramos = d.assign(tramo=(d["peso_corporal_kg"] // 2.5) * 2.5)
    med = tramos.groupby("tramo")["total_kg"].agg(["median", "size"])
    med = med[med["size"] >= 60]
    ax1.plot(med.index, med["median"], color=estilo.MAGENTA, lw=3,
             label="Mediana por tramo de 2,5 kg")
    xs = np.linspace(d["peso_corporal_kg"].min(), d["peso_corporal_kg"].max(), 80)
    ax1.plot(xs, np.exp(reg.intercept) * xs ** reg.slope, color=estilo.TINTA,
             ls="--", lw=2, label=f"Ajuste alométrico  b = {reg.slope:.3f}")
    estilo.titular(ax1, "La fuerza crece con el peso, pero cada vez menos",
                   f"Exponente {reg.slope:.3f} < 1: retornos decrecientes "
                   f"(R² = {reg.rvalue ** 2:.2f})")
    ax1.set_xlabel("Peso corporal (kg)")
    ax1.set_ylabel("Total levantado (kg)")
    ax1.legend(loc="lower right")

    frel = tramos.groupby("tramo")["fuerza_relativa"].agg(["median", "size"])
    frel = frel[frel["size"] >= 60]
    ax2.plot(frel.index, frel["median"], color=estilo.TEAL, lw=3)
    ax2.fill_between(frel.index, frel["median"], color=estilo.TEAL, alpha=0.18)
    pico = frel["median"].idxmax()
    ax2.axvline(pico, color=estilo.MAGENTA, ls="--", lw=2,
                label=f"Máximo en {pico:.0f} kg ({frel['median'].max():.2f}x)")
    estilo.titular(ax2, "Fuerza relativa: dónde está el óptimo",
                   "Total levantado dividido por el peso corporal")
    ax2.set_xlabel("Peso corporal (kg)")
    ax2.set_ylabel("Total / peso corporal")
    ax2.legend()
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a5_peso_fuerza")
    print("  [figura] a5_peso_fuerza.png")


# ===========================================================================
# A6. EDAD Y PICO DE RENDIMIENTO
# ===========================================================================
def a6_edad(df: pd.DataFrame) -> None:
    _sep("A6. EDAD Y PICO DE RENDIMIENTO")

    d = df[df["edad"].notna() & df["puntos_dots"].notna()].copy()
    print(f"  Registros con edad conocida: {len(d):,} ({len(d) / len(df) * 100:.1f}%)")

    poredad = (d.assign(edad_ent=d["edad"].round().astype(int))
                .groupby("edad_ent")
                .agg(n=("puntos_dots", "size"), dots=("puntos_dots", "median"),
                     total=("total_kg", "median"),
                     fuerza_rel=("fuerza_relativa", "median")))
    poredad = poredad[poredad["n"] >= 100]
    pico = poredad["dots"].idxmax()
    print(f"  Pico de rendimiento (DOTS mediano): {pico} anios "
          f"({poredad.loc[pico, 'dots']:.1f} puntos)")

    # Meseta de alto rendimiento: edades con >=98% del maximo
    umbral = poredad["dots"].max() * 0.98
    meseta = poredad[poredad["dots"] >= umbral].index
    print(f"  Meseta de alto rendimiento (>=98% del maximo): "
          f"{meseta.min()}-{meseta.max()} anios")
    RES["edad"] = {"pico_anios": int(pico),
                   "dots_pico": round(float(poredad.loc[pico, "dots"]), 2),
                   "meseta": [int(meseta.min()), int(meseta.max())],
                   "n_con_edad": int(len(d))}

    porgrupo = (d.groupby("grupo_edad", observed=True)
                  .agg(n=("puntos_dots", "size"), dots_mediano=("puntos_dots", "median"),
                       total_mediano=("total_kg", "median"),
                       pct_podio=("es_podio", "mean"))
                  .round(3))
    porgrupo["pct_podio"] = (porgrupo["pct_podio"] * 100).round(1)
    print("\n  POR GRUPO DE EDAD:")
    print(porgrupo.to_string())
    RES["por_grupo_edad"] = porgrupo.to_dict("index")

    # Prueba: el rendimiento difiere entre grupos de edad?
    muestras = [g["puntos_dots"].dropna().values
                for _, g in d.groupby("grupo_edad", observed=True) if len(g) >= 30]
    if len(muestras) >= 2:
        h, ph = stats.kruskal(*muestras)
        print(f"\n  Kruskal-Wallis entre grupos de edad: H={h:.1f}  p={ph:.3e}")
        RES["prueba_edad"] = {"kruskal_H": round(float(h), 2), "p": float(ph)}

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(poredad.index, poredad["dots"], color=estilo.MORADO, lw=3)
    ax.fill_between(poredad.index, poredad["dots"], color=estilo.MORADO, alpha=0.16)
    ax.axvspan(meseta.min(), meseta.max(), color=estilo.AMBAR, alpha=0.18,
               label=f"Meseta de alto rendimiento: {meseta.min()}-{meseta.max()} años")
    ax.axvline(pico, color=estilo.MAGENTA, ls="--", lw=2.2,
               label=f"Pico: {pico} años")
    estilo.titular(ax, "El rendimiento femenino en powerlifting por edad",
                   "Puntos DOTS medianos (rendimiento ajustado por peso corporal); "
                   "solo edades con 100+ registros")
    ax.set_xlabel("Edad (años)")
    ax.set_ylabel("Puntos DOTS (mediana)")
    ax.legend()
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a6_edad_rendimiento")
    print("  [figura] a6_edad_rendimiento.png")


# ===========================================================================
# A7. ARQUETIPOS DE FUERZA
# ===========================================================================
def a7_arquetipos(df: pd.DataFrame) -> None:
    _sep("A7. REPARTO DEL TOTAL ENTRE LOS TRES MOVIMIENTOS")

    reparto = df[["pct_sentadilla", "pct_banca", "pct_peso_muerto"]].describe().T
    reparto = reparto[["mean", "std", "25%", "50%", "75%"]].round(2)
    print("  Contribucion de cada movimiento al total (%):")
    print(reparto.to_string())
    RES["reparto_movimientos"] = reparto.to_dict("index")

    perfiles = (df.groupby("perfil_fuerza")
                  .agg(n=("total_kg", "size"), total_mediano=("total_kg", "median"),
                       dots_mediano=("puntos_dots", "median"),
                       fuerza_rel=("fuerza_relativa", "median"),
                       pct_podio=("es_podio", "mean"))
                  .round(3))
    perfiles["pct_del_total"] = (perfiles["n"] / perfiles["n"].sum() * 100).round(1)
    perfiles["pct_podio"] = (perfiles["pct_podio"] * 100).round(1)
    print("\n  ARQUETIPOS DE FUERZA:")
    print(perfiles.to_string())
    RES["arquetipos"] = perfiles.to_dict("index")

    # El arquetipo se asocia al exito deportivo?
    tabla = pd.crosstab(df["perfil_fuerza"], df["es_podio"])
    chi2, p, gl, _ = stats.chi2_contingency(tabla)
    n = tabla.values.sum()
    v_cramer = np.sqrt(chi2 / (n * (min(tabla.shape) - 1)))
    print(f"\n  Chi-cuadrado perfil vs podio: chi2={chi2:.1f}  gl={gl}  p={p:.3e}")
    print(f"  V de Cramer = {v_cramer:.4f}  "
          f"({'asociacion practicamente nula' if v_cramer < 0.1 else 'asociacion apreciable'})")
    RES["perfil_vs_podio"] = {"chi2": round(float(chi2), 2), "p": float(p),
                              "v_cramer": round(float(v_cramer), 4)}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    for col, etiq, color in [("pct_sentadilla", "Sentadilla", estilo.MORADO),
                             ("pct_banca", "Banca", estilo.MAGENTA),
                             ("pct_peso_muerto", "Peso muerto", estilo.TEAL)]:
        ax1.hist(df[col].dropna(), bins=90, alpha=0.62, label=etiq,
                 color=color, edgecolor="none")
    estilo.titular(ax1, "Cada movimiento aporta una parte estable del total",
                   "Distribución del % del total que representa cada levantamiento")
    ax1.set_xlabel("% del total levantado")
    ax1.set_ylabel("Nº de registros")
    ax1.set_xlim(15, 55)
    ax1.legend()

    ev = (df[df["anio"].between(1990, 2025)]
          .groupby("anio")[["pct_sentadilla", "pct_banca", "pct_peso_muerto"]]
          .median())
    for col, etiq, color in [("pct_sentadilla", "Sentadilla", estilo.MORADO),
                             ("pct_banca", "Banca", estilo.MAGENTA),
                             ("pct_peso_muerto", "Peso muerto", estilo.TEAL)]:
        ax2.plot(ev.index, ev[col], label=etiq, color=color, lw=2.6)
    estilo.titular(ax2, "Evolución del reparto en el tiempo",
                   "Mediana anual del peso de cada movimiento en el total")
    ax2.set_xlabel("Año")
    ax2.set_ylabel("% del total (mediana)")
    ax2.legend()
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a7_arquetipos_fuerza")
    print("  [figura] a7_arquetipos_fuerza.png")


# ===========================================================================
# A8. EFECTO DEL EQUIPAMIENTO
# ===========================================================================
def a8_equipamiento(df: pd.DataFrame) -> None:
    _sep("A8. EFECTO DEL EQUIPAMIENTO")

    poreq = (df.groupby("equipamiento")
               .agg(n=("total_kg", "size"), total_mediano=("total_kg", "median"),
                    dots_mediano=("puntos_dots", "median"),
                    fuerza_rel=("fuerza_relativa", "median"),
                    peso_mediano=("peso_corporal_kg", "median"))
               .sort_values("dots_mediano", ascending=False).round(2))
    print(poreq.to_string())
    RES["por_equipamiento"] = poreq.to_dict("index")

    raw = df[df["tipo_equipamiento"] == "Sin equipamiento (Raw)"]["puntos_dots"].dropna()
    eq = df[df["tipo_equipamiento"] == "Con equipamiento (Equipped)"]["puntos_dots"].dropna()
    t, pt = stats.ttest_ind(eq, raw, equal_var=False)
    u, pu = stats.mannwhitneyu(eq, raw, alternative="two-sided")
    # Tamano del efecto (d de Cohen): mide la magnitud, no solo la significacion
    s_pool = np.sqrt(((len(eq) - 1) * eq.var() + (len(raw) - 1) * raw.var())
                     / (len(eq) + len(raw) - 2))
    d_cohen = (eq.mean() - raw.mean()) / s_pool
    ventaja = (eq.median() - raw.median()) / raw.median() * 100
    print(f"\n  Con equipamiento: mediana {eq.median():.1f} DOTS (n={len(eq):,})")
    print(f"  Sin equipamiento: mediana {raw.median():.1f} DOTS (n={len(raw):,})")
    print(f"  Ventaja del equipamiento: {ventaja:+.1f}%")
    print(f"  t de Welch = {t:.1f} (p={pt:.2e})   Mann-Whitney p={pu:.2e}")
    print(f"  d de Cohen = {d_cohen:.3f} (tamano del efecto)")
    RES["equipamiento"] = {"dots_equipped": round(float(eq.median()), 2),
                           "dots_raw": round(float(raw.median()), 2),
                           "ventaja_pct": round(float(ventaja), 2),
                           "t_welch": round(float(t), 2), "p_welch": float(pt),
                           "p_mannwhitney": float(pu),
                           "d_cohen": round(float(d_cohen), 4)}

    # -----------------------------------------------------------------------
    # CONTROL DEL SESGO DE COMPOSICION
    # -----------------------------------------------------------------------
    # La comparacion anterior es enganosa. El tipo de equipamiento no se
    # asigna al azar: va ligado a la FEDERACION, y las federaciones difieren
    # mucho en nivel competitivo. La modalidad 'Unlimited' aparece sobre todo
    # en circuitos amateur, lo que arrastra su media hacia abajo y hace
    # parecer que el equipamiento perjudica. Se controla de dos maneras.
    print("\n  " + "-" * 68)
    print("  CONTROL DEL SESGO: el equipamiento va ligado a la federacion")
    print("  " + "-" * 68)

    # (a) Comparacion INTRA-ATLETA (pareada): misma atleta compitiendo en
    #     ambas modalidades. Es el control mas limpio posible, porque elimina
    #     de raiz las diferencias de nivel entre personas.
    pares = (df.dropna(subset=["fuerza_relativa"])
               .groupby(["id_atleta", "tipo_equipamiento"])["fuerza_relativa"]
               .median().unstack())
    pares = pares.dropna()
    pares.columns = ["equipada", "sin_equipar"] if list(pares.columns)[0].startswith("Con") \
        else ["sin_equipar", "equipada"]
    print(f"\n  (a) Comparacion pareada intra-atleta: {len(pares):,} atletas han "
          f"competido en\n      ambas modalidades")
    if len(pares) >= 30:
        dif = pares["equipada"] - pares["sin_equipar"]
        w, pw = stats.wilcoxon(pares["equipada"], pares["sin_equipar"])
        ventaja_intra = dif.median() / pares["sin_equipar"].median() * 100
        print(f"      Fuerza relativa mediana con equipamiento : "
              f"{pares['equipada'].median():.3f}")
        print(f"      Fuerza relativa mediana sin equipamiento : "
              f"{pares['sin_equipar'].median():.3f}")
        print(f"      Diferencia mediana intra-atleta: {dif.median():+.3f} "
              f"({ventaja_intra:+.1f}%)")
        print(f"      Wilcoxon pareado: W={w:.0f}  p={pw:.3e}")
        print(f"      -> el equipamiento "
              f"{'SI aporta ventaja' if dif.median() > 0 and pw < 0.05 else 'no aporta ventaja clara'} "
              f"cuando se compara a la misma atleta")
        RES["equipamiento_intra_atleta"] = {
            "n_atletas": int(len(pares)),
            "frel_equipada": round(float(pares["equipada"].median()), 4),
            "frel_sin_equipar": round(float(pares["sin_equipar"].median()), 4),
            "diferencia_mediana": round(float(dif.median()), 4),
            "ventaja_pct": round(float(ventaja_intra), 2),
            "wilcoxon_p": float(pw)}

    # (b) Comparacion dentro del mismo ambito federativo
    print("\n  (b) Dentro del mismo ambito federativo:")
    filas_fed = []
    for ambito in df["ambito_federacion"].dropna().unique():
        sub = df[df["ambito_federacion"] == ambito]
        e = sub[sub["tipo_equipamiento"] == "Con equipamiento (Equipped)"]["fuerza_relativa"].dropna()
        r = sub[sub["tipo_equipamiento"] == "Sin equipamiento (Raw)"]["fuerza_relativa"].dropna()
        if len(e) < 200 or len(r) < 200:
            continue
        u2, pu2 = stats.mannwhitneyu(e, r, alternative="two-sided")
        d2 = (e.median() - r.median()) / r.median() * 100
        print(f"      {ambito:<32} equipada {e.median():.3f} | "
              f"sin equipar {r.median():.3f} | {d2:+.1f}%  p={pu2:.2e}")
        filas_fed.append({"ambito": ambito,
                          "frel_equipada": round(float(e.median()), 4),
                          "frel_sin_equipar": round(float(r.median()), 4),
                          "diferencia_pct": round(float(d2), 2), "p": float(pu2)})
    RES["equipamiento_por_ambito"] = filas_fed

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    orden = poreq.index.tolist()
    datos = [df[df["equipamiento"] == e]["puntos_dots"].dropna().values for e in orden]
    bp = ax1.boxplot(datos, tick_labels=orden, patch_artist=True, showfliers=False,
                     medianprops={"color": "white", "lw": 2})
    for caja, color in zip(bp["boxes"], estilo.SECUENCIA):
        caja.set_facecolor(color)
        caja.set_alpha(0.85)
    estilo.titular(ax1, "Rendimiento según el equipamiento permitido",
                   "Puntos DOTS: normalizan el total por el peso corporal")
    ax1.set_ylabel("Puntos DOTS")
    ax1.tick_params(axis="x", rotation=15)

    cuota = (df[df["anio"].between(1990, 2025)]
             .groupby(["anio", "tipo_equipamiento"]).size().unstack(fill_value=0))
    cuota_pct = cuota.div(cuota.sum(axis=1), axis=0) * 100
    ax2.stackplot(cuota_pct.index, cuota_pct.T.values,
                  labels=cuota_pct.columns,
                  colors=[estilo.MAGENTA, estilo.MORADO], alpha=0.85)
    estilo.titular(ax2, "El powerlifting sin equipamiento se ha impuesto",
                   "Reparto anual de las participaciones por tipo de modalidad")
    ax2.set_xlabel("Año")
    ax2.set_ylabel("% de participaciones")
    ax2.set_ylim(0, 100)
    ax2.legend(loc="lower left")
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a8_equipamiento")
    print("  [figura] a8_equipamiento.png")


# ===========================================================================
# A9. TRAYECTORIA Y PROGRESION
# ===========================================================================
def a9_trayectoria(df: pd.DataFrame) -> None:
    _sep("A9. TRAYECTORIA Y PROGRESION DE LAS ATLETAS")

    porat = df.groupby("id_atleta").agg(
        n=("total_kg", "size"), anios=("anios_trayectoria", "first"))
    print(f"  Competiciones por atleta: mediana {porat['n'].median():.0f}, "
          f"media {porat['n'].mean():.2f}, maximo {porat['n'].max()}")
    print(f"  Atletas con una sola competicion: "
          f"{(porat['n'] == 1).mean() * 100:.1f}%  (abandono temprano)")
    print(f"  Atletas con 10 o mas competiciones: {(porat['n'] >= 10).mean() * 100:.1f}%")
    RES["trayectoria"] = {
        "mediana_competiciones": float(porat["n"].median()),
        "media_competiciones": round(float(porat["n"].mean()), 2),
        "max_competiciones": int(porat["n"].max()),
        "pct_una_sola": round(float((porat["n"] == 1).mean() * 100), 2),
        "pct_diez_o_mas": round(float((porat["n"] >= 10).mean() * 100), 2)}

    prog = (df[df["n_competicion"] <= 20]
            .groupby("n_competicion")
            .agg(n=("total_kg", "size"), dots=("puntos_dots", "median"),
                 total=("total_kg", "median"),
                 mejora=("mejora_kg", "median"),
                 pct_record=("es_record_personal", "mean")))
    prog["pct_record"] = (prog["pct_record"] * 100).round(1)
    print("\n  PROGRESION POR NUMERO DE COMPETICION:")
    print(prog.round(2).head(12).to_string())
    RES["progresion"] = prog.round(2).to_dict("index")

    m = df[df["mejora_kg"].notna()]
    print(f"\n  Mejora entre competiciones consecutivas: "
          f"mediana {m['mejora_kg'].median():+.1f} kg")
    print(f"  Registros que son record personal: "
          f"{df['es_record_personal'].mean() * 100:.1f}%")

    # La mejora se agota con la experiencia? Correlacion mejora vs n_competicion
    sub = df[df["mejora_kg"].notna() & (df["n_competicion"] <= 30)]
    rs, ps = stats.spearmanr(sub["n_competicion"], sub["mejora_kg"])
    print(f"  Correlacion (Spearman) nº competicion vs mejora: "
          f"rho={rs:+.4f}  p={ps:.2e}")
    RES["progresion_decreciente"] = {"spearman": round(float(rs), 4), "p": float(ps),
                                     "mejora_mediana_kg": float(m["mejora_kg"].median())}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    ax1.bar(prog.index, prog["dots"], color=estilo.MORADO, alpha=0.9)
    ax1.set_ylim(prog["dots"].min() * 0.93, prog["dots"].max() * 1.02)
    estilo.titular(ax1, "El rendimiento mejora con la experiencia competitiva",
                   "Puntos DOTS medianos según el número de competición de la atleta")
    ax1.set_xlabel("Nº de competición de la atleta")
    ax1.set_ylabel("Puntos DOTS (mediana)")

    ax2.plot(prog.index, prog["mejora"], color=estilo.MAGENTA, lw=2.8, marker="o", ms=5)
    ax2.axhline(0, color=estilo.GRIS, lw=1.2, ls=":")
    estilo.titular(ax2, "Pero la mejora se agota: rendimientos decrecientes",
                   "Ganancia mediana en kg respecto a la competición anterior")
    ax2.set_xlabel("Nº de competición de la atleta")
    ax2.set_ylabel("Mejora mediana (kg)")
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a9_trayectoria")
    print("  [figura] a9_trayectoria.png")


# ===========================================================================
# A10. BRECHA DE GENERO EN EL TIEMPO
# ===========================================================================
def a10_brecha(df: pd.DataFrame) -> None:
    _sep("A10. BRECHA DE RENDIMIENTO RESPECTO A LOS HOMBRES")

    # DOTS y Wilks aplican coeficientes distintos a hombres y a mujeres, para
    # permitir comparar dentro de cada sexo. Usarlos entre sexos da resultados
    # sin sentido: ratios mayores que 1, es decir, que las mujeres levantan
    # mas. La brecha real se mide con la fuerza relativa (total entre peso
    # corporal), que no incorpora ningun ajuste por sexo.
    print("  Metrica utilizada: FUERZA RELATIVA (total / peso corporal).")
    print("  DOTS y Wilks quedan descartados para comparar sexos porque ya")
    print("  estan normalizados POR sexo (se muestran solo para ilustrarlo).\n")

    ref = pd.read_csv(cfg.REF_MASC)
    ref = ref[ref["n_hombres"] >= 100]
    fem = (df[df["anio"].between(1990, 2025)]
           .groupby(["anio", "equipamiento"])
           .agg(frel_f=("fuerza_relativa", "median"),
                total_f=("total_kg", "median"),
                dots_f=("puntos_dots", "median"),
                n_f=("total_kg", "size")).reset_index())
    fem = fem[fem["n_f"] >= 100]
    comp = fem.merge(ref, left_on=["anio", "equipamiento"],
                     right_on=["anio", "Equipment"], how="inner")
    comp["ratio_frel"] = comp["frel_f"] / comp["fuerza_rel_p50_m"]
    comp["ratio_total"] = comp["total_f"] / comp["total_p50_m"]
    comp["ratio_dots"] = comp["dots_f"] / comp["dots_medio_m"]

    anual = (comp.groupby("anio")
                 .apply(lambda g: pd.Series({
                     "ratio_frel": np.average(g["ratio_frel"], weights=g["n_f"]),
                     "ratio_total": np.average(g["ratio_total"], weights=g["n_f"]),
                     "ratio_dots": np.average(g["ratio_dots"], weights=g["n_f"]),
                     "n_f": g["n_f"].sum()}), include_groups=False))

    reg = stats.linregress(anual.index, anual["ratio_frel"])
    print(f"  FUERZA RELATIVA mujeres/hombres:")
    print(f"    {anual.index[0]}: {anual['ratio_frel'].iloc[0] * 100:.1f}%   "
          f"{anual.index[-1]}: {anual['ratio_frel'].iloc[-1] * 100:.1f}%")
    print(f"    Tendencia: {reg.slope * 100:+.4f} p.p./anio "
          f"(R2={reg.rvalue ** 2:.3f}, p={reg.pvalue:.2e})")
    print(f"  TOTAL ABSOLUTO mujeres/hombres:")
    print(f"    {anual.index[0]}: {anual['ratio_total'].iloc[0] * 100:.1f}%   "
          f"{anual.index[-1]}: {anual['ratio_total'].iloc[-1] * 100:.1f}%")
    print(f"  DOTS (NO valido entre sexos, solo ilustrativo):")
    print(f"    {anual.index[0]}: {anual['ratio_dots'].iloc[0] * 100:.1f}%   "
          f"{anual.index[-1]}: {anual['ratio_dots'].iloc[-1] * 100:.1f}%   "
          f"<- por encima de 100% precisamente porque el indice ya ajusta por sexo")

    if reg.pvalue >= 0.05:
        conclusion = "estable (sin tendencia significativa)"
    elif reg.slope > 0:
        conclusion = "se estrecha"
    else:
        conclusion = "se amplia"
    print(f"\n  CONCLUSION: la brecha de fuerza relativa {conclusion}")
    RES["brecha_genero"] = {
        "metrica": "fuerza relativa (total/peso corporal)",
        "nota": "DOTS y Wilks no son validos entre sexos: llevan coeficientes "
                "distintos por sexo",
        "ratio_frel_inicio": round(float(anual["ratio_frel"].iloc[0]), 4),
        "ratio_frel_fin": round(float(anual["ratio_frel"].iloc[-1]), 4),
        "ratio_total_inicio": round(float(anual["ratio_total"].iloc[0]), 4),
        "ratio_total_fin": round(float(anual["ratio_total"].iloc[-1]), 4),
        "anio_inicio": int(anual.index[0]), "anio_fin": int(anual.index[-1]),
        "pendiente_anual_pp": round(float(reg.slope * 100), 4),
        "r2": round(float(reg.rvalue ** 2), 4), "p": float(reg.pvalue),
        "conclusion": conclusion}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6),
                                   gridspec_kw={"width_ratios": [1.25, 1]})
    ax1.plot(anual.index, anual["ratio_frel"] * 100, color=estilo.MAGENTA, lw=3,
             marker="o", ms=4.5, label="Fuerza relativa (total / peso corporal)")
    ax1.plot(anual.index, anual["ratio_total"] * 100, color=estilo.MORADO,
             lw=2.4, ls="--", label="Total absoluto en kg")
    ax1.plot(anual.index, (reg.intercept + reg.slope * anual.index) * 100,
             color=estilo.GRIS, ls=":", lw=1.8,
             label=f"Tendencia: {reg.slope * 100:+.3f} p.p./año "
                   f"(p={reg.pvalue:.2f})")
    ax1.axhline(100, color=estilo.TINTA, lw=1, alpha=0.5)
    estilo.titular(ax1, "Rendimiento femenino como porcentaje del masculino",
                   f"Medianas ponderadas por volumen y equipamiento. "
                   f"la brecha {conclusion}")
    ax1.set_xlabel("Año")
    ax1.set_ylabel("Mujeres / hombres (%)")
    ax1.legend(loc="center right", fontsize=9.5)

    ax2.plot(anual.index, anual["ratio_dots"] * 100, color=estilo.CORAL, lw=2.8,
             marker="s", ms=4, label="DOTS (índice normalizado por sexo)")
    ax2.plot(anual.index, anual["ratio_frel"] * 100, color=estilo.MAGENTA,
             lw=2.4, label="Fuerza relativa (métrica válida)")
    ax2.axhline(100, color=estilo.TINTA, lw=1.2, alpha=0.6)
    ax2.text(anual.index[1], 101.5, "Paridad aparente", fontsize=9,
             color=estilo.GRIS)
    estilo.titular(ax2, "Por qué DOTS no sirve para comparar sexos",
                   "El índice ya corrige por sexo: da paridad artificial")
    ax2.set_xlabel("Año")
    ax2.set_ylabel("Mujeres / hombres (%)")
    ax2.legend(fontsize=9.5)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a10_brecha_genero")
    print("  [figura] a10_brecha_genero.png")


# ===========================================================================
# A11. CONTROL ANTIDOPAJE
# ===========================================================================
def a11_antidopaje(df: pd.DataFrame) -> None:
    _sep("A11. DECLARACION DE CONTROL ANTIDOPAJE Y RENDIMIENTO")

    # LIMITACION DEL DATO: el campo original solo vale 'Yes' o queda vacio.
    # No existe un "no hubo control" explicito, asi que lo que se compara es
    # "federacion que declara programa de control" frente a "no lo declara".
    print("  Lectura correcta del dato: se compara si la federacion DECLARA")
    print("  programa antidopaje, no si hubo o no control efectivo.\n")

    tab = (df.groupby("control_antidoping")
             .agg(n=("total_kg", "size"), dots_mediano=("puntos_dots", "median"),
                  total_mediano=("total_kg", "median"),
                  fuerza_rel=("fuerza_relativa", "median")).round(3))
    print(tab.to_string())
    RES["antidopaje"] = tab.to_dict("index")

    # El equipamiento es un factor de confusion evidente: las federaciones que
    # no declaran control tienden a permitir mas material. Se compara dentro
    # de cada modalidad para aislar el efecto.
    print("\n  Comparacion dentro de cada modalidad (control del sesgo):")
    filas = []
    for eqp in ["Sin equipamiento (Raw)", "Con equipamiento (Equipped)"]:
        sub = df[df["tipo_equipamiento"] == eqp]
        con = sub[sub["control_antidoping"] == "Control declarado"]["fuerza_relativa"].dropna()
        sin = sub[sub["control_antidoping"] == "Control no declarado"]["fuerza_relativa"].dropna()
        if len(con) < 100 or len(sin) < 100:
            print(f"    {eqp:<28} muestra insuficiente "
                  f"(declarado n={len(con):,}, no declarado n={len(sin):,})")
            continue
        u, pu = stats.mannwhitneyu(sin, con, alternative="two-sided")
        dif = (sin.median() - con.median()) / con.median() * 100
        print(f"    {eqp:<28} declarado {con.median():.3f} | "
              f"no declarado {sin.median():.3f} | dif {dif:+.1f}% | p={pu:.2e}  "
              f"(n={len(con):,} / {len(sin):,})")
        filas.append({"modalidad": eqp,
                      "frel_control_declarado": round(float(con.median()), 4),
                      "frel_control_no_declarado": round(float(sin.median()), 4),
                      "diferencia_pct": round(float(dif), 2), "p": float(pu),
                      "n_declarado": int(len(con)), "n_no_declarado": int(len(sin))})
    RES["antidopaje_controlado"] = filas


# ===========================================================================
# A12. MATRIZ DE CORRELACIONES
# ===========================================================================
def a12_correlaciones(df: pd.DataFrame) -> None:
    _sep("A12. MATRIZ DE CORRELACIONES ENTRE VARIABLES CLAVE")

    cols = ["total_kg", "fuerza_relativa", "puntos_dots", "peso_corporal_kg",
            "edad", "n_competicion", "tasa_acierto_intentos",
            "pct_participacion_femenina", "indice_desigualdad_gen", "idh",
            "pib_per_capita_ppa", "tasa_actividad_femenina"]
    cols = [c for c in cols if c in df.columns]
    corr = df[cols].corr(method="spearman")

    etiquetas = {
        "total_kg": "Total (kg)", "fuerza_relativa": "Fuerza relativa",
        "puntos_dots": "Puntos DOTS", "peso_corporal_kg": "Peso corporal",
        "edad": "Edad", "n_competicion": "Nº competición",
        "tasa_acierto_intentos": "Acierto en intentos",
        "pct_participacion_femenina": "Cuota femenina país",
        "indice_desigualdad_gen": "Desigualdad género (GII)",
        "idh": "IDH", "pib_per_capita_ppa": "PIB per cápita",
        "tasa_actividad_femenina": "Actividad laboral fem."}
    corr_et = corr.rename(index=etiquetas, columns=etiquetas)
    print(corr.round(3).to_string())
    RES["matriz_correlaciones"] = corr.round(4).to_dict()

    fig, ax = plt.subplots(figsize=(11, 9))
    mascara = np.triu(np.ones_like(corr, dtype=bool), k=1)
    m = np.ma.masked_where(mascara, corr.values)
    im = ax.imshow(m, cmap="PuOr_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)))
    ax.set_yticks(range(len(corr)))
    ax.set_xticklabels(corr_et.columns, rotation=45, ha="right", fontsize=9.5)
    ax.set_yticklabels(corr_et.index, fontsize=9.5)
    for i in range(len(corr)):
        for j in range(len(corr)):
            if not mascara[i, j]:
                v = corr.values[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5,
                        color="white" if abs(v) > 0.55 else estilo.TINTA)
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.7, label="Correlación de Spearman")
    ax.set_title("Correlaciones entre rendimiento, perfil y contexto socioeconómico",
                 loc="left", pad=16)
    estilo.pie_de_fuente(fig)
    estilo.guardar(fig, "a12_matriz_correlaciones")
    print("\n  [figura] a12_matriz_correlaciones.png")


def main() -> None:
    df = cargar()
    a1_panorama(df)
    a2_evolucion(df)
    a3_geografia(df)
    a4_igualdad(df)
    a5_peso_fuerza(df)
    a6_edad(df)
    a7_arquetipos(df)
    a8_equipamiento(df)
    a9_trayectoria(df)
    a10_brecha(df)
    a11_antidopaje(df)
    a12_correlaciones(df)

    destino = cfg.REPORTS / "resultados_analisis.json"
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(RES, f, ensure_ascii=False, indent=2, default=str)
    _sep("ANALISIS COMPLETADO")
    print(f"  Resultados numericos : {destino.relative_to(cfg.RAIZ)}")
    print(f"  Figuras              : {cfg.FIGURES.relative_to(cfg.RAIZ)}/ "
          f"({len(list(cfg.FIGURES.glob('*.png')))} imagenes)")


if __name__ == "__main__":
    main()
