"""
Carga el conjunto final en una base SQLite con esquema en estrella, para poder
explotarlo con SQL analitico.

El grano de hechos_participacion es una fila por atleta y competicion.
dim_atleta tiene una fila por atleta y dim_pais_anio una por pais y anio.

Se usa SQLite y no PostgreSQL porque el fichero .db viaja dentro del
repositorio, de modo que cualquiera puede clonarlo y ejecutar las consultas sin
instalar ni levantar un servidor. El SQL empleado es practicamente identico en
ambos motores.

Ejecucion:  python src/base_datos.py
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

BD = cfg.SQL / "powerlifting_femenino.db"

# --- Columnas de la tabla de hechos ---
# Se selecciona un subconjunto analitico en lugar de las 83 columnas: mantiene
# el fichero .db por debajo del limite de 100 MB por fichero de GitHub y evita
# duplicar en la tabla de hechos lo que ya vive en las dimensiones.
HECHOS = [
    "id_atleta", "fecha", "anio", "mes", "decada",
    "iso3", "federacion", "ambito_federacion", "nombre_competicion",
    "equipamiento", "tipo_equipamiento", "control_antidoping",
    "edad", "grupo_edad", "peso_corporal_kg", "categoria_peso",
    "total_kg", "fuerza_relativa", "puntos_dots",
    "kg_sentadilla", "kg_banca", "kg_peso_muerto",
    "pct_sentadilla", "pct_banca", "pct_peso_muerto", "perfil_fuerza",
    "posicion", "es_podio",
    "n_competicion", "es_debut", "total_anterior", "mejor_total_previo",
    "mejora_kg", "es_record_personal",
    "brecha_fuerza_rel_pct",
]

DIM_PAIS = [
    "iso3", "anio", "pais_competicion", "region",
    "pct_participacion_femenina", "n_mujeres_pais_anio", "n_hombres_pais_anio",
    "pib_per_capita_ppa", "grupo_renta", "idh", "idh_femenino", "idh_masculino",
    "indice_desigualdad_gen", "grupo_desigualdad", "indice_desarrollo_gen",
    "tasa_actividad_femenina", "matricula_superior_femenina",
    "esperanza_vida_femenina", "indicadores_imputados",
]

ESQUEMA = """
-- ---------------------------------------------------------------------------
-- Esquema en estrella del proyecto
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS hechos_participacion;
DROP TABLE IF EXISTS dim_pais_anio;
DROP TABLE IF EXISTS dim_atleta;

-- Dimension: una fila por atleta, con su resumen de trayectoria
CREATE TABLE dim_atleta (
    id_atleta              TEXT PRIMARY KEY,
    nombre_atleta          TEXT,
    iso3_principal         TEXT,
    n_competiciones        INTEGER,
    primera_fecha          TEXT,
    ultima_fecha           TEXT,
    anios_trayectoria      REAL,
    mejor_total_kg         REAL,
    mejor_dots             REAL,
    peso_medio_kg          REAL
);

-- Dimension: contexto de pais y anio (procede de las fuentes 2a y 2b)
CREATE TABLE dim_pais_anio (
    iso3                        TEXT NOT NULL,
    anio                        INTEGER NOT NULL,
    pais_competicion            TEXT,
    region                      TEXT,
    pct_participacion_femenina  REAL,
    n_mujeres_pais_anio         INTEGER,
    n_hombres_pais_anio         INTEGER,
    pib_per_capita_ppa          REAL,
    grupo_renta                 TEXT,
    idh                         REAL,
    idh_femenino                REAL,
    idh_masculino               REAL,
    indice_desigualdad_gen      REAL,
    grupo_desigualdad           TEXT,
    indice_desarrollo_gen       REAL,
    tasa_actividad_femenina     REAL,
    matricula_superior_femenina REAL,
    esperanza_vida_femenina     REAL,
    indicadores_imputados       INTEGER,
    PRIMARY KEY (iso3, anio)
);

-- Hechos: una fila por participacion de una atleta en una competicion
CREATE TABLE hechos_participacion (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_atleta              TEXT NOT NULL,
    fecha                  TEXT NOT NULL,
    anio                   INTEGER NOT NULL,
    mes                    INTEGER,
    decada                 TEXT,
    iso3                   TEXT,
    federacion             TEXT,
    ambito_federacion      TEXT,
    nombre_competicion     TEXT,
    equipamiento           TEXT,
    tipo_equipamiento      TEXT,
    control_antidoping     TEXT,
    edad                   REAL,
    grupo_edad             TEXT,
    peso_corporal_kg       REAL,
    categoria_peso         TEXT,
    total_kg               REAL NOT NULL,
    fuerza_relativa        REAL,
    puntos_dots            REAL,
    kg_sentadilla          REAL,
    kg_banca               REAL,
    kg_peso_muerto         REAL,
    pct_sentadilla         REAL,
    pct_banca              REAL,
    pct_peso_muerto        REAL,
    perfil_fuerza          TEXT,
    posicion               REAL,
    es_podio               INTEGER,
    n_competicion          INTEGER,
    es_debut               INTEGER,
    total_anterior         REAL,
    mejor_total_previo     REAL,
    mejora_kg              REAL,
    es_record_personal     INTEGER,
    brecha_fuerza_rel_pct  REAL,
    FOREIGN KEY (id_atleta) REFERENCES dim_atleta (id_atleta),
    FOREIGN KEY (iso3, anio) REFERENCES dim_pais_anio (iso3, anio)
);
"""

INDICES = """
CREATE INDEX idx_hechos_atleta   ON hechos_participacion (id_atleta);
CREATE INDEX idx_hechos_pais     ON hechos_participacion (iso3, anio);
CREATE INDEX idx_hechos_anio     ON hechos_participacion (anio);
CREATE INDEX idx_hechos_equipo   ON hechos_participacion (tipo_equipamiento);
CREATE INDEX idx_hechos_total    ON hechos_participacion (total_kg);
CREATE INDEX idx_atleta_pais     ON dim_atleta (iso3_principal);
"""


def construir() -> None:
    print("=" * 70)
    print("CONSTRUCCION DE LA BASE DE DATOS SQLite")
    print("=" * 70)

    ruta = cfg.DATASET_FINAL_PLANO if cfg.DATASET_FINAL_PLANO.exists() else cfg.DATASET_FINAL
    print(f"\n  Leyendo {ruta.name}...")
    df = pd.read_csv(ruta, low_memory=False)
    print(f"  {len(df):,} filas x {df.shape[1]} columnas")

    if BD.exists():
        BD.unlink()
    con = sqlite3.connect(BD)
    con.executescript(ESQUEMA)
    print("\n  Esquema creado: dim_atleta, dim_pais_anio, hechos_participacion")

    # --- dim_atleta -------------------------------------------------------
    atletas = (df.sort_values("fecha")
                 .groupby("id_atleta")
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
    atletas.to_sql("dim_atleta", con, if_exists="append", index=False)
    print(f"  dim_atleta            {len(atletas):>8,} filas")

    # --- dim_pais_anio ----------------------------------------------------
    paises = (df[DIM_PAIS].drop_duplicates(subset=["iso3", "anio"])
                          .sort_values(["iso3", "anio"]))
    paises["indicadores_imputados"] = paises["indicadores_imputados"].astype(int)
    paises.to_sql("dim_pais_anio", con, if_exists="append", index=False)
    print(f"  dim_pais_anio         {len(paises):>8,} filas")

    # --- hechos_participacion ---------------------------------------------
    hechos = df[HECHOS].copy()
    for c in ["es_podio", "es_debut", "es_record_personal"]:
        hechos[c] = hechos[c].astype("boolean").astype("Int64")
    hechos.to_sql("hechos_participacion", con, if_exists="append", index=False,
                  chunksize=50_000)
    print(f"  hechos_participacion  {len(hechos):>8,} filas")

    con.executescript(INDICES)
    print("\n  6 indices creados")
    con.execute("ANALYZE")
    con.commit()
    con.execute("VACUUM")
    con.close()

    mb = BD.stat().st_size / 1024 ** 2
    print(f"\n  Base de datos: {BD.relative_to(cfg.RAIZ)} ({mb:.1f} MB)")
    if mb > 95:
        print(f"  [AVISO] supera el limite de 100 MB por fichero de GitHub. "
              f"Se versionara comprimida.")
    return mb


def verificar() -> None:
    """Comprueba la integridad del modelo con consultas de control."""
    print("\n" + "=" * 70)
    print("VERIFICACION DE INTEGRIDAD")
    print("=" * 70)
    con = sqlite3.connect(BD)

    pruebas = [
        ("Filas en hechos", "SELECT COUNT(*) FROM hechos_participacion"),
        ("Atletas en la dimension", "SELECT COUNT(*) FROM dim_atleta"),
        ("Combinaciones pais-anio", "SELECT COUNT(*) FROM dim_pais_anio"),
        ("Hechos sin atleta en dim (debe ser 0)",
         """SELECT COUNT(*) FROM hechos_participacion h
            LEFT JOIN dim_atleta a ON h.id_atleta = a.id_atleta
            WHERE a.id_atleta IS NULL"""),
        ("Hechos sin pais-anio en dim (debe ser 0)",
         """SELECT COUNT(*) FROM hechos_participacion h
            LEFT JOIN dim_pais_anio p ON h.iso3 = p.iso3 AND h.anio = p.anio
            WHERE p.iso3 IS NULL"""),
        ("Totales incoherentes con la suma (debe ser 0)",
         """SELECT COUNT(*) FROM hechos_participacion
            WHERE ABS(total_kg - (kg_sentadilla + kg_banca + kg_peso_muerto)) > 2.5"""),
    ]
    for etiqueta, sql in pruebas:
        valor = con.execute(sql).fetchone()[0]
        print(f"  {etiqueta:<42} {valor:>10,}")
    con.close()


if __name__ == "__main__":
    construir()
    verificar()
    print("\n" + "=" * 70)
    print("BASE DE DATOS LISTA")
    print("=" * 70)
