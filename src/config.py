"""Configuracion central de rutas y constantes del proyecto."""
from pathlib import Path

# --- Rutas del proyecto (relativas a la raiz) ---
RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
EXTERNAL = DATA / "external"
REPORTS = RAIZ / "reports"
FIGURES = REPORTS / "figures"
SQL = RAIZ / "sql"
DASHBOARD = RAIZ / "dashboard"

for _d in (RAW, PROCESSED, EXTERNAL, FIGURES, SQL, DASHBOARD):
    _d.mkdir(parents=True, exist_ok=True)

# --- Fuente 1: OpenPowerlifting (dominio publico) ---
URL_OPL = "https://openpowerlifting.gitlab.io/opl-csv/files/openpowerlifting-latest.zip"

# --- Fuente 2a: Banco Mundial (API abierta, sin clave) ---
URL_WB = "https://api.worldbank.org/v2/country/all/indicator/{ind}"
INDICADORES_WB = {
    "NY.GDP.PCAP.PP.KD": "pib_per_capita_ppa",          # PIB per capita (PPA, $ const. 2021)
    "SP.POP.TOTL":       "poblacion_total",             # Poblacion total
    "SL.TLF.CACT.FE.ZS": "tasa_actividad_femenina",     # Tasa actividad laboral mujeres 15+
    "SE.TER.ENRR.FE":    "matricula_superior_femenina", # Matriculacion terciaria femenina (%)
    "SP.DYN.LE00.FE.IN": "esperanza_vida_femenina",     # Esperanza de vida mujeres
    "SH.XPD.CHEX.PC.CD": "gasto_sanitario_pc",          # Gasto sanitario per capita ($)
    "SP.URB.TOTL.IN.ZS": "poblacion_urbana_pct",        # Poblacion urbana (%)
}

# --- Fuente 2b: PNUD / UNDP Human Development Report ---
URL_UNDP = ("https://hdr.undp.org/sites/default/files/2023-24_HDR/"
            "HDR23-24_Composite_indices_complete_time_series.csv")
INDICADORES_UNDP = {
    "hdi":   "idh",                    # Indice de Desarrollo Humano (global)
    "hdi_f": "idh_femenino",           # IDH calculado solo para mujeres
    "hdi_m": "idh_masculino",          # IDH calculado solo para hombres
    "gii":   "indice_desigualdad_gen", # Gender Inequality Index (0 = igualdad)
    "gdi":   "indice_desarrollo_gen",  # Gender Development Index (IDH_f / IDH_m)
    "le_f":  "esperanza_vida_f",       # Componentes femeninos del IDH
    "eys_f": "anios_escolar_esp_f",
    "mys_f": "anios_escolar_medios_f",
    "gni_pc_f": "ingreso_nacional_pc_f",
}

# --- Ficheros de salida ---
F1_RAW = RAW / "fuente1_openpowerlifting_femenino.csv.gz"
F2_WB_RAW = RAW / "fuente2a_worldbank_indicadores.csv"
F2_UNDP_RAW = RAW / "fuente2b_undp_desarrollo_humano.csv"
REF_MASC = EXTERNAL / "referencia_masculina_agregada.csv"
# El conjunto final se versiona comprimido (el CSV plano supera el limite de
# 100 MB por fichero de GitHub). El .csv sin comprimir se genera en local
# porque es el formato que Power BI importa de forma mas directa.
DATASET_FINAL = PROCESSED / "dataset_final_powerlifting_femenino.csv.gz"
DATASET_FINAL_PLANO = PROCESSED / "dataset_final_powerlifting_femenino.csv"

SEMILLA = 42
