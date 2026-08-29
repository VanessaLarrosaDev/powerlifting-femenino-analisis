"""
Exporta el conjunto final como modelo en estrella para Power BI: una tabla de
hechos y tres dimensiones (calendario, pais-anio y atleta).

Se escribe en Parquet y en CSV. Conviene usar el Parquet: ocupa diez veces
menos, carga mucho mas rapido y conserva los tipos, lo que evita los problemas
habituales al importar CSV (fechas leidas como texto, decimales con nulos que
Power BI marca como enteros, booleanos que llegan como la cadena "True").

La tabla de calendario es necesaria porque Power BI la exige, marcada como tal,
para que funcionen las comparativas interanuales y los acumulados. La columna
ambito_analisis etiqueta cada fila segun si el pais es comparable
internacionalmente, y alimenta el filtro de ambito del dashboard.

Ejecucion:  python src/exportar_powerbi.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

DESTINO = cfg.DASHBOARD / "datos"

# Umbral de registros para considerar un pais comparable internacionalmente
UMBRAL_COMPARABLE = 2_000

HECHOS = [
    "id_atleta", "fecha", "iso3",
    "federacion", "ambito_federacion", "nombre_competicion",
    "equipamiento", "tipo_equipamiento", "control_antidoping",
    "edad", "grupo_edad", "peso_corporal_kg", "categoria_peso",
    "total_kg", "fuerza_relativa", "puntos_dots",
    "kg_sentadilla", "kg_banca", "kg_peso_muerto",
    "pct_sentadilla", "pct_banca", "pct_peso_muerto", "perfil_fuerza",
    "posicion", "es_podio",
    "n_competicion", "es_debut", "total_anterior", "mejora_kg",
    "es_record_personal", "brecha_fuerza_rel_pct",
]

DIM_PAIS = [
    "iso3", "anio", "pais_competicion", "region",
    "pct_participacion_femenina", "n_mujeres_pais_anio", "n_hombres_pais_anio",
    "pib_per_capita_ppa", "grupo_renta", "idh", "idh_femenino", "idh_masculino",
    "indice_desigualdad_gen", "grupo_desigualdad", "indice_desarrollo_gen",
    "tasa_actividad_femenina", "matricula_superior_femenina",
    "esperanza_vida_femenina", "indicadores_imputados",
]

resumen: list[dict] = []


def _guardar(df: pd.DataFrame, nombre: str, nota: str = "") -> None:
    """Escribe una tabla en Parquet y en CSV, y anota los tamanos."""
    # Las columnas de tipo 'category' se convierten a texto: Power BI no gana
    # nada con el tipo categorico y algunas versiones lo importan mal.
    salida = df.copy()
    for c in salida.select_dtypes("category").columns:
        salida[c] = salida[c].astype("string")

    ruta_pq = DESTINO / f"{nombre}.parquet"
    salida.to_parquet(ruta_pq, index=False, engine="pyarrow",
                      compression="snappy")
    ruta_csv = DESTINO / f"{nombre}.csv"
    salida.to_csv(ruta_csv, index=False, encoding="utf-8-sig")

    mb_pq = ruta_pq.stat().st_size / 1024 ** 2
    mb_csv = ruta_csv.stat().st_size / 1024 ** 2
    resumen.append({"tabla": nombre, "filas": len(salida),
                    "columnas": salida.shape[1], "mb_parquet": mb_pq,
                    "mb_csv": mb_csv})
    print(f"  {nombre:<18} {len(salida):>8,} filas x {salida.shape[1]:>2} col | "
          f"parquet {mb_pq:>6.1f} MB | csv {mb_csv:>6.1f} MB"
          + (f" | {nota}" if nota else ""))


def exportar() -> None:
    print("=" * 78)
    print("EXPORTACION DEL MODELO PARA POWER BI")
    print("=" * 78)
    DESTINO.mkdir(parents=True, exist_ok=True)

    ruta = cfg.DATASET_FINAL_PLANO if cfg.DATASET_FINAL_PLANO.exists() else cfg.DATASET_FINAL
    print(f"\n  Leyendo {ruta.name}...")
    df = pd.read_csv(ruta, low_memory=False, parse_dates=["fecha"])
    print(f"  {len(df):,} filas x {df.shape[1]} columnas")

    # -- Ambito de analisis: materializa la decision sobre el sesgo de EE.UU.
    volumen = df.groupby("iso3").size()
    comparables = set(volumen[volumen >= UMBRAL_COMPARABLE].index)
    df["ambito_analisis"] = np.where(
        df["iso3"].isin(comparables),
        "Comparable internacionalmente", "Volumen insuficiente")
    cobertura = df["ambito_analisis"].eq("Comparable internacionalmente").mean() * 100
    print(f"\n  Ambito de analisis: {len(comparables)} paises comparables "
          f"(>= {UMBRAL_COMPARABLE:,} registros), {cobertura:.1f}% de los datos")

    print()
    # -- 1. Tabla de hechos ------------------------------------------------
    hechos = df[HECHOS + ["ambito_analisis"]].copy()
    # Clave compuesta: Power BI relaciona por una sola columna con mas soltura
    hechos["clave_pais_anio"] = (hechos["iso3"] + "-"
                                 + hechos["fecha"].dt.year.astype(str))
    # Enteros con soporte de nulos: en Parquet llegan como enteros de verdad,
    # y en CSV como 0/1 (no "True"/"False", que rompe los filtros DAX).
    for c in ["es_podio", "es_debut", "es_record_personal"]:
        hechos[c] = hechos[c].astype("boolean").astype("Int64")
    _guardar(hechos, "hechos")

    # -- 2. Dimension pais-anio --------------------------------------------
    paises = (df[DIM_PAIS].drop_duplicates(subset=["iso3", "anio"])
                          .sort_values(["iso3", "anio"])
                          .reset_index(drop=True))
    paises["ambito_analisis"] = np.where(
        paises["iso3"].isin(comparables),
        "Comparable internacionalmente", "Volumen insuficiente")
    paises["clave_pais_anio"] = paises["iso3"] + "-" + paises["anio"].astype(str)
    paises["indicadores_imputados"] = (paises["indicadores_imputados"]
                                       .astype("boolean").astype("Int64"))
    _guardar(paises, "dim_pais_anio")

    # -- 3. Dimension atleta -----------------------------------------------
    atletas = (df.sort_values("fecha").groupby("id_atleta")
                 .agg(nombre_atleta=("nombre_atleta", "first"),
                      iso3_principal=("iso3", lambda s: s.mode().iloc[0]
                                      if not s.mode().empty else None),
                      n_competiciones=("total_kg", "size"),
                      primera_fecha=("fecha", "min"),
                      ultima_fecha=("fecha", "max"),
                      anios_trayectoria=("anios_trayectoria", "first"),
                      mejor_total_kg=("total_kg", "max"),
                      mejor_dots=("puntos_dots", "max"),
                      peso_medio_kg=("peso_corporal_kg", "mean"))
                 .reset_index())
    atletas["peso_medio_kg"] = atletas["peso_medio_kg"].round(2)
    atletas["anios_trayectoria"] = atletas["anios_trayectoria"].round(2)
    # Segmento de compromiso: alimenta el analisis de retencion del dashboard
    atletas["segmento_trayectoria"] = pd.cut(
        atletas["n_competiciones"], bins=[0, 1, 3, 9, 10_000],
        labels=["Una sola competición", "2-3 competiciones",
                "4-9 competiciones", "10 o más competiciones"])
    _guardar(atletas, "dim_atleta")

    # -- 4. Tabla de calendario --------------------------------------------
    # Continua y sin huecos: requisito para la inteligencia de tiempo.
    inicio, fin = df["fecha"].min().normalize(), df["fecha"].max().normalize()
    fechas = pd.DataFrame({"fecha": pd.date_range(inicio, fin, freq="D")})
    fechas["anio"] = fechas["fecha"].dt.year
    fechas["mes"] = fechas["fecha"].dt.month
    fechas["nombre_mes"] = fechas["fecha"].dt.month.map({
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo",
        6: "Junio", 7: "Julio", 8: "Agosto", 9: "Septiembre",
        10: "Octubre", 11: "Noviembre", 12: "Diciembre"})
    fechas["trimestre"] = "T" + fechas["fecha"].dt.quarter.astype(str)
    fechas["anio_mes"] = fechas["fecha"].dt.strftime("%Y-%m")
    fechas["decada"] = (fechas["anio"] // 10 * 10).astype(str) + "s"
    fechas["dia_semana"] = fechas["fecha"].dt.dayofweek.map({
        0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
        4: "Viernes", 5: "Sábado", 6: "Domingo"})
    fechas["es_fin_de_semana"] = (fechas["fecha"].dt.dayofweek >= 5).astype("Int64")
    _guardar(fechas, "dim_calendario", f"{inicio:%Y} a {fin:%Y}")

    # -- Resumen ------------------------------------------------------------
    r = pd.DataFrame(resumen)
    print(f"\n  {'':<18} {'PARQUET':>14} {'CSV':>14}")
    print(f"  {'TOTAL':<18} {r['mb_parquet'].sum():>11.1f} MB "
          f"{r['mb_csv'].sum():>11.1f} MB")
    print(f"  Reduccion con Parquet: "
          f"{(1 - r['mb_parquet'].sum() / r['mb_csv'].sum()) * 100:.0f}% menos peso")
    print(f"\n  Carpeta: {DESTINO.relative_to(cfg.RAIZ)}")
    print(f"  Siguiente paso: seguir dashboard/GUIA_POWERBI.md")


if __name__ == "__main__":
    exportar()
