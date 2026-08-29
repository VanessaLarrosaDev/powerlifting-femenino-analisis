"""
Descarga y prepara las fuentes del proyecto.

La fuente 1 es OpenPowerlifting, con los resultados de competicion de todo el
mundo, de dominio publico. Se filtra el subconjunto femenino, que es el objeto
de estudio.

La fuente 2 aporta el contexto socioeconomico por pais y anio, y combina la API
del Banco Mundial con los indices compuestos del PNUD.

Ejecucion:  python src/extraccion.py [ruta_csv_opl_local]
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg

# En equipos con antivirus o proxy corporativo que inspecciona TLS, el almacen
# de certificados de Python no reconoce la CA interceptora y toda descarga
# HTTPS falla. 'truststore' delega la validacion al almacen del sistema
# operativo, que si la conoce. Es opcional: si no esta, se sigue sin el.
try:
    import truststore

    truststore.inject_into_ssl()
except ImportError:
    pass

USER_AGENT = "Mozilla/5.0 (proyecto-academico-master-data-analytics)"
BLOQUE_BYTES = 4 * 1024 * 1024


def _descargar(url: str, destino: Path | None = None) -> bytes:
    """Descarga una URL y devuelve los bytes. Cachea en disco si se indica destino."""
    if destino and destino.exists() and destino.stat().st_size > 0:
        print(f"    [cache] {destino.name}")
        return destino.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as r:
        datos = r.read()
    if destino:
        destino.write_bytes(datos)
    return datos


# ---------------------------------------------------------------------------
# FUENTE 1 - OpenPowerlifting
# ---------------------------------------------------------------------------
def extraer_fuente1(ruta_csv_local: Path | None = None) -> pd.DataFrame:
    """
    Lee el volcado completo de OpenPowerlifting por bloques y separa:
      - el subconjunto femenino completo    -> data/raw/      (fuente 1 en bruto)
      - un agregado masculino de referencia -> data/external/ (brecha de genero)
    """
    print("\n" + "=" * 70)
    print("FUENTE 1 | OpenPowerlifting - resultados de competicion")
    print("=" * 70)

    if ruta_csv_local is None:
        print("  Descargando volcado completo (~160 MB comprimido)...")
        crudo = _descargar(cfg.URL_OPL, cfg.RAW / "_opl_descarga.zip")
        with zipfile.ZipFile(io.BytesIO(crudo)) as z:
            nombre = [n for n in z.namelist() if n.endswith(".csv")][0]
            ruta_csv_local = cfg.RAW / "_opl_completo.csv"
            with z.open(nombre) as src, open(ruta_csv_local, "wb") as dst:
                while True:
                    trozo = src.read(BLOQUE_BYTES)
                    if not trozo:
                        break
                    dst.write(trozo)

    print(f"  Leyendo: {Path(ruta_csv_local).name}")
    bloques_f = []
    filas_totales = 0

    for i, bloque in enumerate(pd.read_csv(ruta_csv_local, chunksize=400_000,
                                           low_memory=False), start=1):
        filas_totales += len(bloque)
        bloques_f.append(bloque[bloque["Sex"] == "F"].copy())
        print(f"    bloque {i:>2} | acumuladas {filas_totales:>9,} filas", end="\r")

    print(f"\n  Filas totales en la fuente original : {filas_totales:,}")

    fem = pd.concat(bloques_f, ignore_index=True)
    print(f"  Registros FEMENINOS extraidos       : {len(fem):,}")
    print(f"  Columnas originales                 : {fem.shape[1]}")

    fem.to_csv(cfg.F1_RAW, index=False, compression="gzip")
    mb = cfg.F1_RAW.stat().st_size / 1024 ** 2
    print(f"  -> guardado en {cfg.F1_RAW.relative_to(cfg.RAIZ)} ({mb:.1f} MB)")
    return fem


def extraer_referencia_masculina(ruta_csv_local: Path) -> pd.DataFrame:
    """
    Agregados masculinos por anio y equipamiento, usados como grupo de
    referencia para medir la brecha de rendimiento entre sexos.

    IMPORTANTE - eleccion de la metrica de brecha:
      Los indices DOTS y Wilks usan coeficientes DISTINTOS para hombres y
      mujeres, precisamente para poder comparar dentro de cada sexo. Por eso
      NO sirven para medir una brecha entre sexos: un ratio DOTS de 1,0 no
      significa fuerza equivalente. La brecha fisica real se mide con la
      FUERZA RELATIVA (total levantado / peso corporal), que no incorpora
      ningun ajuste por sexo. Este agregado la calcula explicitamente.
    """
    print("\n" + "=" * 70)
    print("FUENTE 1c | Referencia masculina para la brecha de rendimiento")
    print("=" * 70)

    partes = []
    for bloque in pd.read_csv(ruta_csv_local, chunksize=800_000, low_memory=False,
                              usecols=["Sex", "Date", "Equipment", "Event",
                                       "TotalKg", "BodyweightKg", "Dots"]):
        m = bloque[(bloque["Sex"] == "M") & (bloque["Event"] == "SBD")
                   & bloque["TotalKg"].gt(0) & bloque["BodyweightKg"].gt(30)]
        if not len(m):
            continue
        m = m.assign(anio=m["Date"].str[:4].astype(int),
                     fuerza_rel=m["TotalKg"] / m["BodyweightKg"])
        partes.append(m[["anio", "Equipment", "TotalKg", "BodyweightKg",
                         "Dots", "fuerza_rel"]])

    todo = pd.concat(partes, ignore_index=True)
    ref = (todo.groupby(["anio", "Equipment"], as_index=False)
               .agg(n_hombres=("TotalKg", "size"),
                    total_medio_m=("TotalKg", "mean"),
                    total_p50_m=("TotalKg", "median"),
                    peso_medio_m=("BodyweightKg", "mean"),
                    dots_medio_m=("Dots", "mean"),
                    fuerza_rel_media_m=("fuerza_rel", "mean"),
                    fuerza_rel_p50_m=("fuerza_rel", "median")))
    for c in ["total_medio_m", "total_p50_m", "peso_medio_m", "dots_medio_m",
              "fuerza_rel_media_m", "fuerza_rel_p50_m"]:
        ref[c] = ref[c].round(4)
    ref.to_csv(cfg.REF_MASC, index=False)
    print(f"  {len(todo):,} registros masculinos SBD -> {len(ref):,} "
          f"combinaciones anio-equipamiento")
    print(f"  -> {cfg.REF_MASC.relative_to(cfg.RAIZ)}")
    return ref


def extraer_participacion_por_pais(ruta_csv_local: Path) -> pd.DataFrame:
    """
    Cuenta participaciones por sexo, pais y anio sobre el volcado completo.

    Necesario para calcular la METRICA CENTRAL del estudio: el porcentaje de
    participacion femenina en cada pais y anio. Solo lee 4 columnas, asi que
    es mucho mas rapido que recorrer el fichero entero.
    """
    print("\n" + "=" * 70)
    print("FUENTE 1b | Participacion por sexo, pais y anio")
    print("=" * 70)

    partes = []
    for bloque in pd.read_csv(ruta_csv_local, chunksize=800_000, low_memory=False,
                              usecols=["Sex", "Date", "MeetCountry", "Event"]):
        bloque = bloque[bloque["Sex"].isin(["M", "F"])].copy()
        bloque["anio"] = bloque["Date"].str[:4].astype(int)
        partes.append(
            bloque.groupby(["anio", "MeetCountry", "Sex"], observed=True)
                  .size().reset_index(name="n")
        )

    part = (pd.concat(partes, ignore_index=True)
              .groupby(["anio", "MeetCountry", "Sex"], as_index=False)["n"].sum()
              .pivot(index=["anio", "MeetCountry"], columns="Sex", values="n")
              .fillna(0).astype(int)
              .rename(columns={"F": "n_mujeres_pais_anio", "M": "n_hombres_pais_anio"})
              .reset_index())
    part.columns.name = None
    part["n_total_pais_anio"] = part["n_mujeres_pais_anio"] + part["n_hombres_pais_anio"]
    part["pct_participacion_femenina"] = (
        part["n_mujeres_pais_anio"] / part["n_total_pais_anio"] * 100
    ).round(2)

    destino = cfg.EXTERNAL / "participacion_por_pais_anio.csv"
    part.to_csv(destino, index=False)
    print(f"  -> {len(part):,} combinaciones pais-anio "
          f"({destino.relative_to(cfg.RAIZ)})")
    return part


# ---------------------------------------------------------------------------
# FUENTE 2a - Banco Mundial
# ---------------------------------------------------------------------------
def extraer_worldbank() -> pd.DataFrame:
    """Descarga los indicadores del Banco Mundial via su API publica (sin clave)."""
    print("\n" + "=" * 70)
    print("FUENTE 2a | Banco Mundial - indicadores socioeconomicos")
    print("=" * 70)

    tablas = []
    for codigo, nombre in cfg.INDICADORES_WB.items():
        url = (cfg.URL_WB.format(ind=codigo)
               + "?format=json&per_page=20000&date=1990:2024")
        datos = json.loads(_descargar(url).decode("utf-8"))
        if len(datos) < 2 or datos[1] is None:
            print(f"  [aviso] sin datos para {codigo}")
            continue
        df = pd.DataFrame([
            {"iso3": r["countryiso3code"],
             "pais_wb": r["country"]["value"],
             "anio": int(r["date"]),
             nombre: r["value"]}
            for r in datos[1] if r["countryiso3code"]
        ])
        tablas.append(df.set_index(["iso3", "pais_wb", "anio"]))
        print(f"  {nombre:<32} {len(df):>7,} observaciones")

    wb = pd.concat(tablas, axis=1).reset_index()
    wb.to_csv(cfg.F2_WB_RAW, index=False)
    print(f"  -> {wb.shape[0]:,} filas x {wb.shape[1]} columnas "
          f"({cfg.F2_WB_RAW.relative_to(cfg.RAIZ)})")
    return wb


# ---------------------------------------------------------------------------
# FUENTE 2b - PNUD / UNDP
# ---------------------------------------------------------------------------
def extraer_undp() -> pd.DataFrame:
    """Descarga los indices compuestos del PNUD y los pasa a formato largo."""
    print("\n" + "=" * 70)
    print("FUENTE 2b | PNUD (UNDP) - desarrollo humano y desigualdad de genero")
    print("=" * 70)

    crudo = _descargar(cfg.URL_UNDP, cfg.RAW / "_undp_descarga.csv")
    ancho = pd.read_csv(io.BytesIO(crudo), encoding="latin-1")
    print(f"  Fichero original: {ancho.shape[0]} paises x {ancho.shape[1]} columnas")

    registros = []
    for prefijo, nombre in cfg.INDICADORES_UNDP.items():
        # Coincidencia EXACTA '<prefijo>_<anio>'. Es imprescindible usar regex
        # estricto: un simple startswith('hdi_') tambien capturaria 'hdi_f_1990'
        # y 'hdi_m_1990', generando anios duplicados por pais.
        patron = re.compile(rf"^{re.escape(prefijo)}_(\d{{4}})$")
        cols = [c for c in ancho.columns if patron.fullmatch(c)]
        if not cols:
            print(f"  [aviso] no se encuentra el indicador '{prefijo}'")
            continue
        largo = ancho.melt(id_vars=["iso3", "country"], value_vars=cols,
                           var_name="col", value_name=nombre)
        largo["anio"] = largo["col"].str.split("_").str[-1].astype(int)
        registros.append(largo.drop(columns="col")
                              .set_index(["iso3", "country", "anio"]))
        print(f"  {nombre:<32} {len(cols):>3} anios")

    undp = pd.concat(registros, axis=1).reset_index()
    undp = undp.rename(columns={"country": "pais_undp"})
    undp = undp[undp["iso3"].notna() & ~undp["iso3"].astype(str).str.startswith("ZZ")]
    undp.to_csv(cfg.F2_UNDP_RAW, index=False)
    print(f"  -> {undp.shape[0]:,} filas x {undp.shape[1]} columnas "
          f"({cfg.F2_UNDP_RAW.relative_to(cfg.RAIZ)})")
    return undp


if __name__ == "__main__":
    local = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    extraer_fuente1(local)
    if local is None:
        local = cfg.RAW / "_opl_completo.csv"
    extraer_referencia_masculina(local)
    extraer_participacion_por_pais(local)
    extraer_worldbank()
    extraer_undp()
    print("\n" + "=" * 70)
    print("EXTRACCION COMPLETADA")
    print("=" * 70)
