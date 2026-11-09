"""Configuración del sitio. Cambia aquí el nombre y el dominio cuando los elijas."""

SITE_NAME = "Data Center Job USA"
SITE_TAGLINE = "Data center tech jobs with the pay up front"
SITE_URL = "https://datacenterjobusa.com"
CONTACT_EMAIL = "hello@datacenterjobusa.com"  # buzón en Zoho Mail (plan gratis)
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
    "Construcción": "Construction site",
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
MIN_ROLE_STATE_OPENINGS = 5  # "tipo de trabajo × estado" tiene página propia con al menos estas vacantes (y 2 avisos distintos)

# Enlace de la encuesta de turnos (Google Forms, Tally, etc.). Vacío = el sitio dice "muy pronto".
SURVEY_URL = "https://docs.google.com/forms/d/e/1FAIpQLSdAiL_Nd9-OX5mNSFFdpO6MuF6_aGw-_2hpg5V9P-P706oPVQ/viewform"

# Formulario de suscripción ("Send me jobs"). Hoy va a un Google Form de la cuenta de Enmanuel
# ("DCJ Job Alerts"; respuestas en la hoja "DCJ Job Alerts (respuestas)" en Drive). La cuenta de Buttondown
# que había antes no existía y los correos se perdían. Cuando haya un servicio de newsletter, cambia estas
# dos líneas: NEWSLETTER_ACTION al endpoint y NEWSLETTER_FIELDS a los nombres de campo que espere.
NEWSLETTER_ACTION = "https://docs.google.com/forms/d/e/1FAIpQLSfbmj05TnX5Ee-bcC_w9KFdpqQvHRAYD1Jz51CApgX53AurcA/formResponse"
NEWSLETTER_FIELDS = {"email": "entry.97542317", "phone": "entry.1281027727", "state": "entry.1454022816",
                     "company": "entry.1956447035", "source": "entry.1474231209", "page": "entry.466877246"}

# Google Analytics 4: pega aquí el ID de medición ("G-XXXXXXXXXX", en Admin > Flujos de datos de tu propiedad).
# Vacío = el sitio no carga ninguna analítica.
GA4_ID = "G-RPPV8TW7WJ"
# ID del proyecto de Microsoft Clarity (clarity.microsoft.com). Vacío = sin Clarity.
CLARITY_ID = "zajlzfhozy"

# Verificación del sitio en Pinterest (meta p:domain_verify; el código es público por diseño)
PINTEREST_VERIFY = "5b8c6128565e50b5589f43b699e77268"

POST_JOB_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfzxQ_P8s06lyesFXN__cagUqwp0443kYG9-Hx6B89lp-KJ6g/viewform"

# Producto digital "Job-Ready Kit" (PDF). Pega aquí el enlace de compra de la tienda donde lo vendas
# (Gumroad, Lemon Squeezy o un Payment Link de Stripe). Vacío = la página dice "muy pronto" y recoge correos.
KIT_URL = "https://buy.stripe.com/6oUcN47nibWsaue7cHeIw03"
KIT_PRICE = "$27"

# Clave de IndexNow (pública por diseño: el sitio la sirve en /<clave>.txt para avisar a Bing y Yandex de empleos nuevos).
INDEXNOW_KEY = "80f6b05d5c7bb5703a404c84f4d306ef"

# Planes para empresas (páginas Employers y Post a job). pay_url = Payment Link de Stripe de ese plan.
# En Stripe pon "After payment → redirect" a POST_JOB_URL para que la empresa mande los datos del empleo.
# pay_url vacío = el botón abre el formulario y se factura por correo.
JOB_PLANS = [
    {"name": "Job listing", "price": "$99", "term": "for 30 days", "pay_url": "https://buy.stripe.com/6oUfZgazu5y40TE7cHeIw00",
     "features": ["Live within 24 hours", "Shown with pay, per diem, housing and schedule", "In every matching state, city, company and job-type page",
                  "Linked straight to your phone, email or career page"]},
    {"name": "Featured listing", "price": "$199", "term": "for 30 days", "pay_url": "https://buy.stripe.com/fZueVcbDyf8EfOy9kPeIw01",
     "features": ["Everything in Job listing", "Pinned at the top of the home page and your state and job-type pages",
                  "\"Featured\" badge in every list", "Up to 5 openings in one listing"]},
    {"name": "Company page", "price": "$299", "term": "per month", "pay_url": "https://buy.stripe.com/9B6bJ04b66C8byi54zeIw02",
     "features": ["All your openings featured, unlimited", "Your company page kept at the top of Companies",
                  "A short paragraph in your words about pay, schedule and crews", "Same-day updates"]},
]

# Tipos de trabajo que se pueden elegir en la ventana emergente de alertas (se guardan en el campo "source").
JOB_ALERT_TYPES = ["Entry level / no experience", "Data center technician", "Critical facilities", "Cabling & fiber",
                   "Electrical", "Controls & BMS", "Travel jobs with per diem"]
