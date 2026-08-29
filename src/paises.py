"""
Traduce los nombres de pais de OpenPowerlifting a codigo ISO 3166-1 alfa-3,
que es la clave de union con el Banco Mundial y el PNUD.

Hace falta porque OpenPowerlifting usa convenciones propias ("USA", "England",
"Czechia", "N.Ireland") y las otras dos fuentes usan ISO3.

Las cuatro naciones britanicas se agregan a GBR, ya que ni el Banco Mundial ni
el PNUD publican indicadores desagregados por nacion constituyente. Los
territorios dependientes sin serie propia se asignan a su estado soberano.
"""
from __future__ import annotations

import unicodedata

# --- Mapa principal: nombre en OpenPowerlifting -> ISO3 ---
NOMBRE_A_ISO3: dict[str, str] = {
    # America del Norte
    "USA": "USA", "United States": "USA", "Canada": "CAN", "Mexico": "MEX",
    # Reino Unido y naciones constituyentes  -> se agregan a GBR
    "UK": "GBR", "England": "GBR", "Scotland": "GBR", "Wales": "GBR",
    "N.Ireland": "GBR", "Northern Ireland": "GBR", "Great Britain": "GBR",
    # Europa occidental y del norte
    "Ireland": "IRL", "France": "FRA", "Germany": "DEU", "Spain": "ESP",
    "Portugal": "PRT", "Italy": "ITA", "Netherlands": "NLD", "Belgium": "BEL",
    "Luxembourg": "LUX", "Switzerland": "CHE", "Austria": "AUT",
    "Denmark": "DNK", "Norway": "NOR", "Sweden": "SWE", "Finland": "FIN",
    "Iceland": "ISL", "Greenland": "GRL", "Faroe Islands": "FRO",
    "Monaco": "MCO", "Andorra": "AND", "Liechtenstein": "LIE",
    "San Marino": "SMR", "Malta": "MLT", "Gibraltar": "GIB",
    # Europa central y del este
    "Poland": "POL", "Czechia": "CZE", "Czech Republic": "CZE",
    "Slovakia": "SVK", "Hungary": "HUN", "Slovenia": "SVN", "Croatia": "HRV",
    "Serbia": "SRB", "Bosnia and Herzegovina": "BIH", "Montenegro": "MNE",
    "North Macedonia": "MKD", "Macedonia": "MKD", "Albania": "ALB",
    "Kosovo": "XKX", "Greece": "GRC", "Cyprus": "CYP", "Turkey": "TUR",
    "Bulgaria": "BGR", "Romania": "ROU", "Moldova": "MDA",
    "Belarus": "BLR", "Ukraine": "UKR", "Russia": "RUS",
    "Lithuania": "LTU", "Latvia": "LVA", "Estonia": "EST",
    # Caucaso y Asia central
    "Georgia": "GEO", "Armenia": "ARM", "Azerbaijan": "AZE",
    "Kazakhstan": "KAZ", "Uzbekistan": "UZB", "Kyrgyzstan": "KGZ",
    "Tajikistan": "TJK", "Turkmenistan": "TKM", "Mongolia": "MNG",
    # Asia oriental y sudoriental
    "China": "CHN", "Japan": "JPN", "South Korea": "KOR", "Korea": "KOR",
    "North Korea": "PRK", "Taiwan": "TWN", "Hong Kong": "HKG",
    "Macau": "MAC", "Macao": "MAC", "Vietnam": "VNM", "Thailand": "THA",
    "Malaysia": "MYS", "Singapore": "SGP", "Indonesia": "IDN",
    "Philippines": "PHL", "Myanmar": "MMR", "Cambodia": "KHM",
    "Laos": "LAO", "Brunei": "BRN", "East Timor": "TLS",
    # Asia meridional
    "India": "IND", "Pakistan": "PAK", "Bangladesh": "BGD",
    "Sri Lanka": "LKA", "Nepal": "NPL", "Bhutan": "BTN",
    "Maldives": "MDV", "Afghanistan": "AFG",
    # Oriente Medio
    "Iran": "IRN", "Iraq": "IRQ", "Israel": "ISR", "Palestine": "PSE",
    "Lebanon": "LBN", "Jordan": "JOR", "Syria": "SYR",
    "Saudi Arabia": "SAU", "UAE": "ARE", "United Arab Emirates": "ARE",
    "Qatar": "QAT", "Kuwait": "KWT", "Bahrain": "BHR", "Oman": "OMN",
    "Yemen": "YEM",
    # Africa
    "Egypt": "EGY", "Libya": "LBY", "Tunisia": "TUN", "Algeria": "DZA",
    "Morocco": "MAR", "Sudan": "SDN", "South Sudan": "SSD",
    "Ethiopia": "ETH", "Eritrea": "ERI", "Djibouti": "DJI",
    "Somalia": "SOM", "Kenya": "KEN", "Uganda": "UGA", "Tanzania": "TZA",
    "Rwanda": "RWA", "Burundi": "BDI", "Nigeria": "NGA", "Ghana": "GHA",
    "Ivory Coast": "CIV", "Cote d'Ivoire": "CIV", "Senegal": "SEN",
    "Mali": "MLI", "Burkina Faso": "BFA", "Niger": "NER", "Chad": "TCD",
    "Cameroon": "CMR", "Gabon": "GAB", "Congo": "COG",
    "DR Congo": "COD", "Angola": "AGO", "Zambia": "ZMB",
    "Zimbabwe": "ZWE", "Malawi": "MWI", "Mozambique": "MOZ",
    "Botswana": "BWA", "Namibia": "NAM", "South Africa": "ZAF",
    "Lesotho": "LSO", "Eswatini": "SWZ", "Swaziland": "SWZ",
    "Madagascar": "MDG", "Mauritius": "MUS", "Seychelles": "SYC",
    "Benin": "BEN", "Togo": "TGO", "Guinea": "GIN", "Liberia": "LBR",
    "Sierra Leone": "SLE", "Gambia": "GMB", "Mauritania": "MRT",
    "Cape Verde": "CPV", "Reunion": "REU",
    # America Central y Caribe
    "Guatemala": "GTM", "El Salvador": "SLV", "Honduras": "HND",
    "Nicaragua": "NIC", "Costa Rica": "CRI", "Panama": "PAN",
    "Belize": "BLZ", "Cuba": "CUB", "Dominican Republic": "DOM",
    "Haiti": "HTI", "Puerto Rico": "PRI", "Jamaica": "JAM",
    "Trinidad and Tobago": "TTO", "Barbados": "BRB", "Bahamas": "BHS",
    "Aruba": "ABW", "Curacao": "CUW", "Cayman Islands": "CYM",
    "Bermuda": "BMU", "US Virgin Islands": "VIR",
    "Antigua and Barbuda": "ATG", "Saint Lucia": "LCA",
    "Grenada": "GRD", "Dominica": "DMA",
    "Saint Vincent and the Grenadines": "VCT",
    "Saint Kitts and Nevis": "KNA",
    # America del Sur
    "Colombia": "COL", "Venezuela": "VEN", "Ecuador": "ECU", "Peru": "PER",
    "Bolivia": "BOL", "Brazil": "BRA", "Chile": "CHL", "Argentina": "ARG",
    "Uruguay": "URY", "Paraguay": "PRY", "Guyana": "GUY",
    "Suriname": "SUR", "French Guiana": "GUF",
    # Oceania
    "Australia": "AUS", "New Zealand": "NZL", "Fiji": "FJI",
    "Papua New Guinea": "PNG", "Samoa": "WSM", "American Samoa": "ASM",
    "Tonga": "TON", "Vanuatu": "VUT", "Solomon Islands": "SLB",
    "New Caledonia": "NCL", "Guam": "GUM", "Palau": "PLW",
    "Micronesia": "FSM", "Marshall Islands": "MHL", "Kiribati": "KIR",
    "Nauru": "NRU", "Tuvalu": "TUV", "Tahiti": "PYF",
    "French Polynesia": "PYF", "Cook Islands": "COK", "Niue": "NIU",
    # Territorios y variantes detectados al validar los datos reales
    "Isle of Man": "IMN", "British Virgin Islands": "VGB",
    "Cabo Verde": "CPV", "The Gambia": "GMB",
    "Netherlands Antilles": "CUW",  # disuelta en 2010; sucesor con serie propia
    "Transnistria": "MDA",          # region de facto dentro de Moldavia
    # Estados historicos: se asignan a su sucesor principal
    "USSR": "RUS", "Soviet Union": "RUS", "Yugoslavia": "SRB",
    "Czechoslovakia": "CZE", "West Germany": "DEU", "East Germany": "DEU",
    "Serbia and Montenegro": "SRB",
}

# --- Region continental (para agrupar en el dashboard) ---
ISO3_A_REGION: dict[str, str] = {
    **{k: "America del Norte" for k in ["USA", "CAN", "MEX", "GRL", "BMU"]},
    **{k: "Europa" for k in [
        "GBR", "IRL", "FRA", "DEU", "ESP", "PRT", "ITA", "NLD", "BEL", "LUX",
        "CHE", "AUT", "DNK", "NOR", "SWE", "FIN", "ISL", "FRO", "MCO", "AND",
        "LIE", "SMR", "MLT", "GIB", "POL", "CZE", "SVK", "HUN", "SVN", "HRV",
        "SRB", "BIH", "MNE", "MKD", "ALB", "XKX", "GRC", "CYP", "BGR", "ROU",
        "MDA", "BLR", "UKR", "RUS", "LTU", "LVA", "EST", "TUR", "IMN"]},
    **{k: "Asia" for k in [
        "GEO", "ARM", "AZE", "KAZ", "UZB", "KGZ", "TJK", "TKM", "MNG", "CHN",
        "JPN", "KOR", "PRK", "TWN", "HKG", "MAC", "VNM", "THA", "MYS", "SGP",
        "IDN", "PHL", "MMR", "KHM", "LAO", "BRN", "TLS", "IND", "PAK", "BGD",
        "LKA", "NPL", "BTN", "MDV", "AFG", "IRN", "IRQ", "ISR", "PSE", "LBN",
        "JOR", "SYR", "SAU", "ARE", "QAT", "KWT", "BHR", "OMN", "YEM"]},
    **{k: "Africa" for k in [
        "EGY", "LBY", "TUN", "DZA", "MAR", "SDN", "SSD", "ETH", "ERI", "DJI",
        "SOM", "KEN", "UGA", "TZA", "RWA", "BDI", "NGA", "GHA", "CIV", "SEN",
        "MLI", "BFA", "NER", "TCD", "CMR", "GAB", "COG", "COD", "AGO", "ZMB",
        "ZWE", "MWI", "MOZ", "BWA", "NAM", "ZAF", "LSO", "SWZ", "MDG", "MUS",
        "SYC", "BEN", "TGO", "GIN", "LBR", "SLE", "GMB", "MRT", "CPV", "REU"]},
    **{k: "America Latina y Caribe" for k in [
        "GTM", "SLV", "HND", "NIC", "CRI", "PAN", "BLZ", "CUB", "DOM", "HTI",
        "PRI", "JAM", "TTO", "BRB", "BHS", "ABW", "CUW", "CYM", "VIR", "ATG",
        "LCA", "GRD", "DMA", "VCT", "KNA", "COL", "VEN", "ECU", "PER", "BOL",
        "BRA", "CHL", "ARG", "URY", "PRY", "GUY", "SUR", "GUF", "VGB"]},
    **{k: "Oceania" for k in [
        "AUS", "NZL", "FJI", "PNG", "WSM", "ASM", "TON", "VUT", "SLB", "NCL",
        "GUM", "PLW", "FSM", "MHL", "KIR", "NRU", "TUV", "PYF", "COK", "NIU"]},
}


def _normalizar(texto: str) -> str:
    """Quita acentos, espacios sobrantes y unifica mayusculas para comparar."""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.split()).strip().lower()


# Indice auxiliar normalizado, para tolerar variaciones de escritura
_INDICE = {_normalizar(k): v for k, v in NOMBRE_A_ISO3.items()}


def a_iso3(nombre) -> str | None:
    """Traduce un nombre de pais de OpenPowerlifting a su codigo ISO3."""
    if nombre is None:
        return None
    clave = _normalizar(nombre)
    if not clave or clave in ("nan", "none"):
        return None
    return _INDICE.get(clave)


def a_region(iso3) -> str:
    """Devuelve la region continental de un codigo ISO3."""
    return ISO3_A_REGION.get(iso3, "Sin asignar")


def sin_mapear(nombres) -> list[str]:
    """Lista los nombres de pais que aun no tienen traduccion a ISO3."""
    faltan = {n for n in nombres if n is not None and a_iso3(n) is None
              and _normalizar(n) not in ("nan", "none", "")}
    return sorted(faltan)
