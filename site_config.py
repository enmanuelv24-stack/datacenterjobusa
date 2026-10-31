"""Configuración del sitio. Cambia aquí el nombre y el dominio cuando los elijas."""

SITE_NAME = "Data Center Job USA"
SITE_TAGLINE = "Data center tech jobs with the pay up front"
SITE_URL = "https://datacenterjobusa.com"
OWNER_BLURB = ("Built by a working data center technician in Texas who got tired of job boards "
               "that hide the pay and mix our jobs with call centers.")

# Categorías del recolector (en español) -> nombre público en inglés
ROLE_EN = {
    "Instalaciones críticas": "Critical facilities",
    "Técnico de data center (DCT)": "Data center technician",
    "Instalación / red": "Install & network",
    "Controles / BMS": "Controls & BMS",
    "Energía / generación": "Power & generators",
    "Eléctrico": "Electrical",
    "Mecánico / HVAC": "Mechanical & HVAC",
    "Soporte TI": "IT support",
    "Operador": "Operations center",
    "Otro técnico": "Other technician",
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "Washington, D.C.",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}

MIN_CITY_OPENINGS = 3  # una ciudad tiene página propia si tiene al menos estas vacantes

# Enlace de la encuesta de turnos (Google Forms, Tally, etc.). Vacío = el sitio dice "muy pronto".
SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdAiL_Nd9-OX5mNSFFdpO6MuF6_aGw-_2hpg5V9P-P706oPVQ/viewform"
