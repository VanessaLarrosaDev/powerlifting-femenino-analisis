"""
Convierte las fuentes en bruto en el conjunto de datos final.

Carga los registros femeninos de OpenPowerlifting, los limpia, construye las
variables derivadas y los une con el contexto socioeconomico del Banco Mundial
y el PNUD por pais ISO3 y anio.

Cada paso de limpieza anota cuantas filas descarta y por que, y el registro se
guarda en reports/registro_limpieza.csv para poder justificar las decisiones.

Ejecucion:  python src/transformacion.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg
import paises

# --- Umbrales de plausibilidad (justificados en el informe) ---
PESO_MIN, PESO_MAX = 30.0, 250.0     # kg de peso corporal
EDAD_MIN, EDAD_MAX = 10, 90          # anios
TOTAL_MIN, TOTAL_MAX = 20.0, 1000.0  # kg levantados en el total
FUERZA_REL_MAX = 12.0                # total / peso corporal (limite fisiologico)

registro: list[dict] = []


def _log(paso: str, antes: int, despues: int, motivo: str) -> None:
    """Anota el efecto de un paso de limpieza para la trazabilidad."""
    eliminadas = antes - despues
    registro.append({"paso": paso, "filas_antes": antes, "filas_despues": despues,
                     "eliminadas": eliminadas,
                     "pct_eliminado": round(eliminadas / antes * 100, 3) if antes else 0,
                     "motivo": motivo})
    print(f"  {paso:<38} {antes:>9,} -> {despues:>9,}  "
          f"(-{eliminadas:,}; {eliminadas / antes * 100:.2f}%)" if antes else "")


# ===========================================================================
# 1. CARGA
# ===========================================================================
def cargar_fuente1() -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("1. CARGA DE LA FUENTE 1")
    print("=" * 70)
    df = pd.read_csv(cfg.F1_RAW, low_memory=False)
    print(f"  Registros femeninos en bruto: {df.shape[0]:,} x {df.shape[1]} columnas")
    return df


# ===========================================================================
# 2. LIMPIEZA
# ===========================================================================
def limpiar(df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("2. LIMPIEZA")
    print("=" * 70)

    n0 = len(df)

    # -- 2.1 Duplicados exactos --------------------------------------------
    df = df.drop_duplicates()
    _log("2.1 Duplicados exactos", n0, len(df),
         "Filas identicas en todas las columnas: mismo resultado cargado dos veces")

    # -- 2.2 Tipos de datos ------------------------------------------------
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    num = ["Age", "BodyweightKg", "TotalKg", "Dots", "Wilks", "Glossbrenner",
           "Goodlift", "Best3SquatKg", "Best3BenchKg", "Best3DeadliftKg",
           "Squat1Kg", "Squat2Kg", "Squat3Kg", "Bench1Kg", "Bench2Kg",
           "Bench3Kg", "Deadlift1Kg", "Deadlift2Kg", "Deadlift3Kg"]
    for c in num:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    n = len(df)
    df = df[df["Date"].notna()]
    _log("2.2 Fecha invalida", n, len(df), "Sin fecha no se puede situar en el tiempo")

    # -- 2.3 Disciplina: solo powerlifting completo ------------------------
    # Solo 'SBD' (sentadilla + banca + peso muerto). Comparar un total de SBD
    # con uno de solo-banca no tiene sentido, y el objeto de estudio es el
    # powerlifting completo.
    n = len(df)
    df = df[df["Event"] == "SBD"]
    _log("2.3 Solo modalidad completa (SBD)", n, len(df),
         "Se excluyen pruebas parciales (solo banca, solo peso muerto...)")

    # -- 2.4 Competiciones sancionadas -------------------------------------
    n = len(df)
    df = df[df["Sanctioned"] == "Yes"]
    _log("2.4 Solo competicion sancionada", n, len(df),
         "Garantiza arbitraje oficial y homologacion de las marcas")

    # -- 2.5 Marcas validas en los tres movimientos ------------------------
    # En OpenPowerlifting un valor NEGATIVO significa intento FALLADO y un
    # valor nulo que no hay dato. Para el analisis de rendimiento exigimos
    # una marca valida (positiva) en los tres movimientos y en el total.
    n = len(df)
    validas = (df["Best3SquatKg"] > 0) & (df["Best3BenchKg"] > 0) & \
              (df["Best3DeadliftKg"] > 0) & (df["TotalKg"] > 0)
    df = df[validas]
    _log("2.5 Marca valida en los 3 movimientos", n, len(df),
         "Se excluyen nulos y valores negativos (intentos fallidos o descalificaciones)")

    # -- 2.6 Coherencia del total ------------------------------------------
    # El total debe coincidir con la suma de los tres mejores levantamientos.
    n = len(df)
    suma = df["Best3SquatKg"] + df["Best3BenchKg"] + df["Best3DeadliftKg"]
    df = df[(df["TotalKg"] - suma).abs() <= 2.5]
    _log("2.6 Total coherente con la suma", n, len(df),
         "Tolerancia de 2,5 kg (redondeos de disco); descarta errores de carga")

    # -- 2.7 Rangos plausibles ---------------------------------------------
    n = len(df)
    df = df[df["BodyweightKg"].between(PESO_MIN, PESO_MAX)]
    _log("2.7 Peso corporal plausible", n, len(df),
         f"Fuera de [{PESO_MIN}, {PESO_MAX}] kg o ausente: dato no fiable")

    n = len(df)
    df = df[df["TotalKg"].between(TOTAL_MIN, TOTAL_MAX)]
    _log("2.8 Total plausible", n, len(df), f"Fuera de [{TOTAL_MIN}, {TOTAL_MAX}] kg")

    n = len(df)
    df = df[(df["TotalKg"] / df["BodyweightKg"]) <= FUERZA_REL_MAX]
    _log("2.9 Fuerza relativa plausible", n, len(df),
         f"Total/peso > {FUERZA_REL_MAX} es fisiologicamente imposible")

    # -- 2.10 Edad: se conserva la fila, se anula el valor imposible -------
    # La edad falta en ~38% de los registros. Eliminar esas filas destruiria
    # una parte enorme del historico, asi que se mantienen con edad nula y se
    # marca la ausencia; los analisis por edad usan el subconjunto con dato.
    imposibles = (~df["Age"].between(EDAD_MIN, EDAD_MAX)) & df["Age"].notna()
    print(f"  2.10 Edades imposibles anuladas         {imposibles.sum():,} "
          f"(fuera de [{EDAD_MIN}, {EDAD_MAX}] anios)")
    df.loc[imposibles, "Age"] = np.nan
    registro.append({"paso": "2.10 Edad imposible -> nulo", "filas_antes": len(df),
                     "filas_despues": len(df), "eliminadas": 0, "pct_eliminado": 0,
                     "motivo": f"{imposibles.sum()} edades fuera de rango anuladas "
                               "sin eliminar la fila"})

    # -- 2.11 Normalizacion de texto ---------------------------------------
    for c in ["Name", "Division", "Federation", "MeetName", "MeetTown"]:
        df[c] = df[c].astype("string").str.strip()
    df["Tested"] = df["Tested"].fillna("No especificado")
    df["ParentFederation"] = df["ParentFederation"].fillna("Independiente")

    print(f"\n  RESULTADO DE LA LIMPIEZA: {len(df):,} filas "
          f"({len(df) / n0 * 100:.1f}% de las originales)")
    return df.reset_index(drop=True)


# ===========================================================================
# 3. INGENIERIA DE VARIABLES
# ===========================================================================
def transformar(df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("3. INGENIERIA DE VARIABLES")
    print("=" * 70)
    n_ini = df.shape[1]

    # -- 3.1 Identificador anonimo y dimension temporal --------------------
    df["id_atleta"] = df["Name"].map(
        lambda x: hashlib.sha1(str(x).encode("utf-8")).hexdigest()[:12])
    df["anio"] = df["Date"].dt.year
    df["mes"] = df["Date"].dt.month
    df["trimestre"] = df["Date"].dt.quarter
    df["decada"] = (df["anio"] // 10 * 10).astype(str) + "s"
    print("  3.1 Tiempo e identificador     : id_atleta, anio, mes, trimestre, decada")

    # -- 3.2 Geografia ------------------------------------------------------
    df["iso3"] = df["MeetCountry"].map(paises.a_iso3)
    df["region"] = df["iso3"].map(paises.a_region)
    df["pais_competicion"] = df["MeetCountry"]
    df["iso3_atleta"] = df["Country"].map(paises.a_iso3)
    sin = df["iso3"].isna().sum()
    print(f"  3.2 Geografia                  : iso3, region "
          f"({sin:,} filas sin ISO3 = {sin / len(df) * 100:.3f}%)")

    # -- 3.3 Rendimiento absoluto y relativo -------------------------------
    df["fuerza_relativa"] = (df["TotalKg"] / df["BodyweightKg"]).round(3)
    for mov, col in [("sentadilla", "Best3SquatKg"), ("banca", "Best3BenchKg"),
                     ("peso_muerto", "Best3DeadliftKg")]:
        df[f"kg_{mov}"] = df[col]
        df[f"pct_{mov}"] = (df[col] / df["TotalKg"] * 100).round(2)
        df[f"rel_{mov}"] = (df[col] / df["BodyweightKg"]).round(3)
    df["ratio_banca_sentadilla"] = (df["Best3BenchKg"] / df["Best3SquatKg"]).round(3)
    df["ratio_muerto_sentadilla"] = (df["Best3DeadliftKg"] / df["Best3SquatKg"]).round(3)
    print("  3.3 Rendimiento                : fuerza_relativa, kg/pct/rel por "
          "movimiento, ratios")

    # -- 3.4 Perfil de fuerza (arquetipo) ----------------------------------
    # Movimiento en el que la atleta destaca mas respecto a la media del
    # conjunto: revela si es dominante en sentadilla, banca o peso muerto.
    z = pd.DataFrame({
        m: (df[f"pct_{m}"] - df[f"pct_{m}"].mean()) / df[f"pct_{m}"].std()
        for m in ["sentadilla", "banca", "peso_muerto"]})
    df["perfil_fuerza"] = z.idxmax(axis=1).map({
        "sentadilla": "Dominante en sentadilla",
        "banca": "Dominante en banca",
        "peso_muerto": "Dominante en peso muerto"})
    print("  3.4 Perfil de fuerza           : perfil_fuerza (arquetipo dominante)")

    # -- 3.5 Intentos: tasa de acierto tecnico -----------------------------
    cols_int = ["Squat1Kg", "Squat2Kg", "Squat3Kg", "Bench1Kg", "Bench2Kg",
                "Bench3Kg", "Deadlift1Kg", "Deadlift2Kg", "Deadlift3Kg"]
    intentos = df[cols_int]
    df["intentos_registrados"] = intentos.notna().sum(axis=1)
    df["intentos_validos"] = (intentos > 0).sum(axis=1)
    df["tasa_acierto_intentos"] = np.where(
        df["intentos_registrados"] >= 6,
        (df["intentos_validos"] / df["intentos_registrados"] * 100).round(1),
        np.nan)
    df["tiene_detalle_intentos"] = df["intentos_registrados"] >= 6
    print(f"  3.5 Intentos                   : tasa_acierto_intentos "
          f"({df['tiene_detalle_intentos'].mean() * 100:.1f}% con detalle completo)")

    # -- 3.6 Categorias legibles -------------------------------------------
    df["grupo_edad"] = pd.cut(
        df["Age"], bins=[10, 18, 23, 30, 40, 50, 60, 90],
        labels=["Sub-18", "18-23 (junior)", "24-30", "31-40",
                "41-50 (master)", "51-60 (master)", "60+ (master)"],
        right=False)
    df["categoria_peso"] = pd.cut(
        df["BodyweightKg"], bins=[30, 47, 52, 57, 63, 69, 76, 84, 250],
        labels=["-47 kg", "47-52 kg", "52-57 kg", "57-63 kg", "63-69 kg",
                "69-76 kg", "76-84 kg", "+84 kg"], right=False)
    df["tipo_equipamiento"] = np.where(
        df["Equipment"].isin(["Raw", "Wraps"]), "Sin equipamiento (Raw)",
        "Con equipamiento (Equipped)")
    # El campo original solo toma el valor 'Yes' o queda vacio. La ausencia no
    # significa que no hubiera control, sino que la federacion no lo declara;
    # las etiquetas lo reflejan para no inducir a una lectura equivocada.
    df["control_antidoping"] = np.where(
        df["Tested"] == "Yes", "Control declarado", "Control no declarado")
    df["ambito_federacion"] = np.where(
        df["ParentFederation"].isin(["IPF"]), "Internacional (IPF)",
        np.where(df["ParentFederation"] == "Independiente",
                 "Federacion independiente", "Otra federacion internacional"))
    print("  3.6 Categorias                 : grupo_edad, categoria_peso, "
          "tipo_equipamiento, control_antidoping, ambito_federacion")

    # -- 3.7 Resultado deportivo -------------------------------------------
    df["posicion"] = pd.to_numeric(df["Place"], errors="coerce")
    df["es_podio"] = df["posicion"].le(3).fillna(False)
    df["es_primera"] = df["posicion"].eq(1).fillna(False)
    df["descalificada"] = df["Place"].astype(str).isin(["DQ", "DD"])
    print("  3.7 Resultado                  : posicion, es_podio, es_primera")

    # -- 3.8 Trayectoria de la atleta --------------------------------------
    # Variables longitudinales: requieren ordenar por atleta y fecha.
    df = df.sort_values(["id_atleta", "Date"]).reset_index(drop=True)
    g = df.groupby("id_atleta", sort=False)
    df["n_competicion"] = g.cumcount() + 1
    df["es_debut"] = df["n_competicion"] == 1
    df["total_anterior"] = g["TotalKg"].shift(1)
    df["mejora_kg"] = (df["TotalKg"] - df["total_anterior"]).round(1)
    df["mejora_pct"] = (df["mejora_kg"] / df["total_anterior"] * 100).round(2)
    df["dias_desde_anterior"] = g["Date"].diff().dt.days
    df["mejor_total_previo"] = g["TotalKg"].transform(
        lambda s: s.cummax().shift(1))
    df["es_record_personal"] = df["TotalKg"] > df["mejor_total_previo"]
    df["total_competiciones_atleta"] = g["TotalKg"].transform("size")
    df["anios_trayectoria"] = (
        g["Date"].transform("max") - g["Date"].transform("min")).dt.days / 365.25
    print(f"  3.8 Trayectoria                : n_competicion, mejora_kg, "
          f"es_record_personal ({df['id_atleta'].nunique():,} atletas unicas)")

    print(f"\n  Columnas: {n_ini} -> {df.shape[1]}  (+{df.shape[1] - n_ini} nuevas)")
    return df


# ===========================================================================
# 4. UNION CON LA FUENTE 2 Y LOS AGREGADOS
# ===========================================================================
def _extender_indicadores(tabla: pd.DataFrame, anio_min: int,
                          anio_max: int) -> pd.DataFrame:
    """
    Extiende una tabla de indicadores pais-anio a todo el periodo de estudio.

    PROBLEMA: los indicadores del Banco Mundial y del PNUD se publican con
    retraso (llegan hasta 2022-2024) y empiezan en 1990, mientras que las
    competiciones cubren 1975-2026. Sin tratamiento, el 39% de los registros
    quedaria sin contexto socioeconomico.

    DECISION: se propaga el ultimo valor conocido hacia adelante y el primero
    hacia atras, dentro de cada pais. Es defendible porque el IDH, el indice
    de desigualdad de genero o el PIB per capita son series muy inerciales:
    varian poco de un anio al siguiente. Se marca cada fila imputada en la
    columna 'indicadores_imputados' para poder excluirlas en los analisis
    que exijan dato observado.
    """
    cols = [c for c in tabla.columns if c not in ("iso3", "anio")]
    rejilla = pd.MultiIndex.from_product(
        [tabla["iso3"].unique(), range(anio_min, anio_max + 1)],
        names=["iso3", "anio"]).to_frame(index=False)
    ext = rejilla.merge(tabla, on=["iso3", "anio"], how="left")
    ext["_observado"] = ext[cols].notna().any(axis=1)
    ext = ext.sort_values(["iso3", "anio"])
    ext[cols] = ext.groupby("iso3")[cols].ffill()
    ext[cols] = ext.groupby("iso3")[cols].bfill()
    return ext


def unir_fuentes(df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("4. UNION DE LAS DOS FUENTES DE DATOS")
    print("=" * 70)
    a_min, a_max = int(df["anio"].min()), int(df["anio"].max())

    # -- 4.1 Banco Mundial --------------------------------------------------
    wb = pd.read_csv(cfg.F2_WB_RAW)
    wb = wb.drop(columns=["pais_wb"]).drop_duplicates(subset=["iso3", "anio"])
    n_cols_wb = wb.shape[1] - 2
    wb = _extender_indicadores(wb, a_min, a_max).rename(
        columns={"_observado": "wb_observado"})
    antes = len(df)
    df = df.merge(wb, on=["iso3", "anio"], how="left", validate="m:1")
    cob = df["pib_per_capita_ppa"].notna().mean() * 100
    print(f"  4.1 Banco Mundial (2a)  | +{n_cols_wb} columnas | "
          f"cobertura {cob:.1f}% | filas {antes:,} -> {len(df):,}")

    # -- 4.2 PNUD -----------------------------------------------------------
    undp = pd.read_csv(cfg.F2_UNDP_RAW)
    undp = undp.drop(columns=["pais_undp"]).drop_duplicates(subset=["iso3", "anio"])
    n_cols_undp = undp.shape[1] - 2
    undp = _extender_indicadores(undp, a_min, a_max).rename(
        columns={"_observado": "undp_observado"})
    df = df.merge(undp, on=["iso3", "anio"], how="left", validate="m:1")
    cob = df["indice_desigualdad_gen"].notna().mean() * 100
    print(f"  4.2 PNUD / UNDP   (2b)  | +{n_cols_undp} columnas | "
          f"cobertura {cob:.1f}% | filas {len(df):,}")

    # Transparencia: marcar si el contexto socioeconomico viene imputado
    df["indicadores_imputados"] = ~(df["wb_observado"].fillna(False)
                                    & df["undp_observado"].fillna(False))
    print(f"      -> {df['indicadores_imputados'].mean() * 100:.1f}% de filas con "
          f"algun indicador propagado (marcado en 'indicadores_imputados')")

    # -- 4.3 Participacion femenina por pais y anio -------------------------
    part = pd.read_csv(cfg.EXTERNAL / "participacion_por_pais_anio.csv")
    df = df.merge(part, left_on=["pais_competicion", "anio"],
                  right_on=["MeetCountry", "anio"], how="left", validate="m:1")
    df = df.drop(columns=["MeetCountry_y"], errors="ignore")
    print(f"  4.3 Participacion femenina por pais-anio | "
          f"cobertura {df['pct_participacion_femenina'].notna().mean() * 100:.1f}%")

    # -- 4.4 Referencia masculina: brecha de rendimiento entre sexos --------
    # No se usa DOTS para comparar sexos: DOTS y Wilks aplican coeficientes
    # distintos a hombres y a mujeres, justamente para permitir comparaciones
    # dentro de cada sexo, de modo que un ratio de 1,0 entre sexos no significa
    # fuerza equivalente. La brecha fisica se mide con la fuerza relativa
    # (total / peso corporal), que no lleva ajuste por sexo.
    ref = pd.read_csv(cfg.REF_MASC)
    ref = ref[ref["n_hombres"] >= 100]  # estabilidad del grupo de referencia
    df = df.merge(ref[["anio", "Equipment", "total_medio_m", "peso_medio_m",
                       "fuerza_rel_p50_m", "n_hombres"]],
                  on=["anio", "Equipment"], how="left", validate="m:1")
    df["brecha_total_pct"] = ((df["TotalKg"] - df["total_medio_m"])
                              / df["total_medio_m"] * 100).round(2)
    df["brecha_fuerza_rel_pct"] = ((df["fuerza_relativa"] - df["fuerza_rel_p50_m"])
                                   / df["fuerza_rel_p50_m"] * 100).round(2)
    print(f"  4.4 Referencia masculina | brecha_total_pct, "
          f"brecha_fuerza_rel_pct (cobertura "
          f"{df['fuerza_rel_p50_m'].notna().mean() * 100:.1f}%)")

    # -- 4.5 Variables derivadas del cruce ----------------------------------
    df["brecha_idh_genero"] = (df["idh_femenino"] / df["idh_masculino"]).round(4)
    df["pib_per_capita_miles"] = (df["pib_per_capita_ppa"] / 1000).round(2)
    df["grupo_desigualdad"] = pd.cut(
        df["indice_desigualdad_gen"], bins=[0, 0.10, 0.20, 0.35, 1.0],
        labels=["Muy baja desigualdad", "Baja desigualdad",
                "Desigualdad media", "Alta desigualdad"])
    # Los cuartiles de renta se calculan sobre la distribucion de paises, no de
    # filas. Con Estados Unidos concentrando el 68% de los registros, un qcut
    # por filas define los cortes segun la renta estadounidense y acaba
    # clasificando como "renta baja" a paises que no lo son. Un pais debe
    # situarse respecto a los demas paises, no respecto al volumen de datos.
    renta_pais = df.groupby("iso3")["pib_per_capita_ppa"].mean().dropna()
    cortes = np.unique(renta_pais.quantile([0, 0.25, 0.50, 0.75, 1.0]).values)
    cortes[0], cortes[-1] = -np.inf, np.inf
    df["grupo_renta"] = pd.cut(
        df["pib_per_capita_ppa"], bins=cortes,
        labels=["Renta baja", "Renta media-baja", "Renta media-alta",
                "Renta alta"][:len(cortes) - 1])
    print("  4.5 Derivadas del cruce  | brecha_idh_genero, grupo_desigualdad, "
          "grupo_renta")

    return df


# ===========================================================================
# 5. SELECCION FINAL Y GUARDADO
# ===========================================================================
COLUMNAS_FINALES = [
    # Identificacion y tiempo
    "id_atleta", "Name", "Date", "anio", "mes", "trimestre", "decada",
    # Geografia
    "pais_competicion", "iso3", "region", "MeetState", "MeetTown", "MeetName",
    # Competicion
    "Federation", "ParentFederation", "ambito_federacion", "Division",
    "Equipment", "tipo_equipamiento", "control_antidoping",
    # Perfil de la atleta
    "Age", "grupo_edad", "BodyweightKg", "categoria_peso", "WeightClassKg",
    # Rendimiento
    "TotalKg", "fuerza_relativa", "Dots", "Wilks", "Goodlift",
    "kg_sentadilla", "kg_banca", "kg_peso_muerto",
    "pct_sentadilla", "pct_banca", "pct_peso_muerto",
    "rel_sentadilla", "rel_banca", "rel_peso_muerto",
    "ratio_banca_sentadilla", "ratio_muerto_sentadilla", "perfil_fuerza",
    # Ejecucion tecnica
    "intentos_registrados", "intentos_validos", "tasa_acierto_intentos",
    # Resultado
    "posicion", "es_podio", "es_primera",
    # Trayectoria
    "n_competicion", "es_debut", "total_anterior", "mejor_total_previo",
    "mejora_kg", "mejora_pct", "dias_desde_anterior", "es_record_personal",
    "total_competiciones_atleta", "anios_trayectoria",
    # Contexto: participacion y brecha
    "n_mujeres_pais_anio", "n_hombres_pais_anio", "pct_participacion_femenina",
    "brecha_total_pct", "brecha_fuerza_rel_pct", "fuerza_rel_p50_m",
    # Contexto: Banco Mundial (fuente 2a)
    "pib_per_capita_ppa", "pib_per_capita_miles", "grupo_renta",
    "poblacion_total", "tasa_actividad_femenina",
    "matricula_superior_femenina", "esperanza_vida_femenina",
    "gasto_sanitario_pc", "poblacion_urbana_pct",
    # Contexto: PNUD (fuente 2b)
    "idh", "idh_femenino", "idh_masculino", "brecha_idh_genero",
    "indice_desigualdad_gen", "grupo_desigualdad", "indice_desarrollo_gen",
    "anios_escolar_esp_f", "ingreso_nacional_pc_f",
    # Trazabilidad del cruce
    "indicadores_imputados",
]


def guardar(df: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "=" * 70)
    print("5. CONJUNTO DE DATOS FINAL")
    print("=" * 70)

    faltan = [c for c in COLUMNAS_FINALES if c not in df.columns]
    if faltan:
        print(f"  [aviso] columnas ausentes: {faltan}")
    cols = [c for c in COLUMNAS_FINALES if c in df.columns]
    final = df[cols].sort_values(["Date", "id_atleta"]).reset_index(drop=True)

    final = final.rename(columns={
        "Name": "nombre_atleta", "Date": "fecha", "Age": "edad",
        "BodyweightKg": "peso_corporal_kg", "TotalKg": "total_kg",
        "Dots": "puntos_dots", "Wilks": "puntos_wilks",
        "Goodlift": "puntos_goodlift", "Equipment": "equipamiento",
        "Federation": "federacion", "ParentFederation": "federacion_matriz",
        "Division": "division", "WeightClassKg": "categoria_peso_oficial",
        "MeetName": "nombre_competicion", "MeetTown": "ciudad_competicion",
        "MeetState": "region_competicion",
    })

    # Redondeo de decimales: reduce el tamano del fichero a la mitad sin
    # perder precision relevante (los kg se miden en saltos de 0,5).
    for c in final.select_dtypes("float").columns:
        final[c] = final[c].round(3)

    final.to_csv(cfg.DATASET_FINAL, index=False, encoding="utf-8",
                 compression="gzip")
    final.to_csv(cfg.DATASET_FINAL_PLANO, index=False, encoding="utf-8")
    mb = cfg.DATASET_FINAL.stat().st_size / 1024 ** 2
    mb_plano = cfg.DATASET_FINAL_PLANO.stat().st_size / 1024 ** 2

    print(f"  FORMA FINAL : {final.shape[0]:,} filas x {final.shape[1]} columnas")
    print(f"  Versionado  : {cfg.DATASET_FINAL.name} ({mb:.1f} MB comprimido)")
    print(f"  Local/PowerBI: {cfg.DATASET_FINAL_PLANO.name} ({mb_plano:.1f} MB)")
    print(f"  Periodo     : {final['fecha'].min():%Y-%m-%d} a "
          f"{final['fecha'].max():%Y-%m-%d}")
    print(f"  Atletas     : {final['id_atleta'].nunique():,}")
    print(f"  Paises      : {final['iso3'].nunique()}")
    print(f"  Federaciones: {final['federacion'].nunique()}")

    req_filas = "CUMPLE" if final.shape[0] >= 50_000 else "NO CUMPLE"
    req_cols = "CUMPLE" if final.shape[1] >= 20 else "NO CUMPLE"
    print(f"\n  Requisito >= 50.000 filas : {req_filas} ({final.shape[0]:,})")
    print(f"  Requisito >= 20 columnas  : {req_cols} ({final.shape[1]})")

    # Registro de trazabilidad de la limpieza
    pd.DataFrame(registro).to_csv(
        cfg.REPORTS / "registro_limpieza.csv", index=False, encoding="utf-8")
    print(f"  Trazabilidad: reports/registro_limpieza.csv")

    # Diccionario de datos
    dic = pd.DataFrame({
        "columna": final.columns,
        "tipo": [str(t) for t in final.dtypes],
        "nulos_pct": (final.isna().mean() * 100).round(2).values,
        "valores_unicos": [final[c].nunique() for c in final.columns],
        "ejemplo": [final[c].dropna().iloc[0] if final[c].notna().any() else ""
                    for c in final.columns],
    })
    dic.to_csv(cfg.REPORTS / "diccionario_datos.csv", index=False, encoding="utf-8")
    print(f"  Diccionario : reports/diccionario_datos.csv")
    return final


if __name__ == "__main__":
    d = cargar_fuente1()
    d = limpiar(d)
    d = transformar(d)
    d = unir_fuentes(d)
    guardar(d)
    print("\n" + "=" * 70)
    print("TRANSFORMACION COMPLETADA")
    print("=" * 70)
