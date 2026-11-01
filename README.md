# Data Center Job USA

Bolsa de trabajo para técnicos de data center en EE.UU., con el salario por delante.
Las vacantes salen directo de las páginas de empleo de cada empresa y el sitio se reconstruye solo cada día.

## Qué hay aquí

| Archivo | Para qué sirve |
|---|---|
| `collector.py` | Recolecta vacantes (Amazon, Microsoft, Google, Greenhouse, Ashby, Workday) y las limpia: título, ciudad, estado, salario por hora, categoría, nivel. |
| `build_site.py` | Genera el sitio estático en `site/`: inicio con filtros, páginas por empresa, estado, ciudad y vacante, comparador de salarios, sitemap. |
| `site_config.py` | Nombre del sitio, dominio y textos. **Aquí cambias el nombre y el dominio.** |
| `content/*.html` | Guías (certificaciones, turnos). Para agregar una guía, copia una y cámbiale el texto. |
| `test_collector.py` | Pruebas del recolector. |
| `build_sheet.py` | Hoja de Excel para revisar los datos. |
| `.github/workflows/daily.yml` | Lo que corre solo cada día en GitHub. |
| `data/` | Datos crudos y limpios. |

No necesita instalar nada: solo Python 3.10 o más nuevo.

## Correrlo en tu computadora

```bash
python collector.py --out data      # recolecta vacantes en vivo
python build_site.py --out site     # construye el sitio
python -m http.server -d site 8000  # ábrelo en http://localhost:8000
```

## Dónde está publicado

- Sitio: https://datacenterjobusa.com (dominio en GoDaddy, cuenta de Enmanuel; renovación manual, vence 30 oct 2027).
- Código: https://github.com/enmanuelv24-stack/datacenterjobusa (GitHub Pages, fuente "GitHub Actions").
- Se actualiza solo todos los días a las 6:17 am hora de Texas. Para forzarlo: **Actions > Actualizar sitio > Run workflow**.
- Para cambiar algo: edita el archivo en GitHub (o súbelo de nuevo con "Add file > Upload files") y el sitio se reconstruye solo.

DNS en GoDaddy: cuatro registros A en `@` (185.199.108.153, .109.153, .110.153, .111.153) y un CNAME `www` a `enmanuelv24-stack.github.io`.

## Empresas que se leen hoy

| Empresa | Tipo | Cómo se lee |
|---|---|---|
| Amazon (AWS) | Operador | API de amazon.jobs |
| Microsoft, Google, Oracle | Operador | API pública de su sitio de empleos |
| Equinix | Operador | Workday |
| Cologix | Operador | Lever |
| CoreWeave, xAI, Nebius | Operador (nube IA) | Greenhouse |
| Crusoe, Lambda | Operador (nube IA) | Ashby |
| Introl | Contratista de despliegue | HTML de introl.com/careers |
| TDS (Total Deployment Solutions) | Contratista de despliegue | Greenhouse |
| Network Connex (antes NTI Connect) | Contratista de cableado | Lever (solo puestos de data center) |
| AFL | Contratista de cableado | Phenom (solo puestos de data center) |
| Compu Dynamics | Contratista eléctrico | Greenhouse |
| Rosendin | Contratista eléctrico | Su sitio (admin-ajax); solo electricistas de campo |
| Holder Construction | Constructora de data centers | Greenhouse; solo técnicos de obra por hora |
| QTS | Operador | Workday |
| Black Box | Contratista de cableado y despliegue | Oracle HCM (API) |
| Vision Technologies | Contratista de cableado | Loxo (lista en HTML) |
| M.C. Dean | Eléctrico y operación de instalaciones críticas | iCIMS (API) |
| E2 Optics | Contratista de cableado ISP (hyperscale) | iCIMS clásico (HTML) |
| ADB Companies | Fibra ISP/OSP y empalme en data center | UKG/UltiPro (API) |
| The Archetype Strategy | Proveedor de técnicos ISP/fibra para data centers (Tye/Abilene TX y todo EE. UU.; nivel subcontratista) | JazzHR (lista HTML + página por puesto con "Pay:") |
| MidPoint Technology Group | Contratista de cableado/data center (Columbia MD; Oracle Abilene); hoy sin vacantes abiertas | Lever (API) |
| Align | Contratista de cableado de data center (foremen y técnicos; Sterling, Plano, Phoenix, Detroit…) | Greenhouse (API) |
| Telvero | Sub de fibra/ISP hyperscale (Abilene, Columbus, Bridgeport AL); publica pago y per diem | CareerPlug (HTML + página por puesto) |
| SRI Telecom | Sub ISP/fibra (300+ técnicos; Memphis, Fairfax IA, Atlanta, San Antonio) | ApplicantPro (API JSON) |
| Team LINX | Contratista de bajo voltaje / ISP en construcción de data centers (Abilene, Dallas, El Paso, SLC, Cheyenne) | WordPress (tabla HTML + página por puesto con "Pay:") |

Pendientes: Total Team Communications (Houston; contratista ISP/fibra de Oracle, no tiene bolsa pública en su sitio),
Salute Mission Critical (usa ADP, difícil de leer), Megawatt Construction (no tiene bolsa pública),
Digital Realty (su Workday no responde desde fuera), WWT (ADP), Wachter (seguridad, no DC), Telaid (subcontrata), Vantage, Meta, CBRE/JLL, DPR, Turner, Mortenson.

## Agregar una empresa

- Si usa Greenhouse: agrega `"nombre-del-board": "Empresa"` en `GREENHOUSE_BOARDS` dentro de `collector.py`.
- Si usa Ashby: igual, en `ASHBY_ORGS`.
- Si usa Lever: igual, en `LEVER_ORGS`. Si la empresa también publica puestos que no son de data center (fibra, torres), agrégala a `DC_ONLY`.
- Si usa Workday: agrega una línea en `WORKDAY_SITES` con `(empresa, host, tenant, sitio)`, tomados de la dirección de su página de empleos.

Nunca agregues Indeed, LinkedIn ni otros agregadores: sus términos lo prohíben.

## Después de publicar

1. Da de alta el sitio en Google Search Console y envía `sitemap.xml`.
2. Conecta el formulario de suscripción a un servicio de newsletter (beehiiv, Buttondown o Kit). El formulario de hoy es de muestra y no guarda correos.
3. Pon el enlace de tu encuesta de turnos en `SURVEY_URL` dentro de `site_config.py`.

## Páginas y SEO
- `index.html` (filtros: estado, empresa, tipo, pago mínimo, nivel, experiencia, beneficios; secciones "By type of work" y "By level"), `roles/` y `levels/` (páginas por categoría), `new-jobs.html` (últimos 7 días) + `feed.xml` (RSS),
  `entry-level-jobs.html` (principiantes, guía y FAQ), `travel-jobs.html` (per diem/hospedaje/rotación), `salaries.html`, `states/`, `cities/`, `companies/`, `jobs/`.
- Logos: favicon de cada empleador vía Google (`COMPANY_DOMAINS` en build_site.py) con avatar de letras de respaldo. Ícono propio: `favicon.svg`, `apple-touch-icon.png`, imagen para compartir `og.png`.
- Datos estructurados: JobPosting (con validThrough, identifier, pago del empleador) en cada vacante, BreadcrumbList en empresa/estado/ciudad/vacante, WebSite/Organization en inicio y About, FAQ en principiantes.
- `sitemap.xml` es un índice → `sitemap-pages.xml` (lastmod = hoy) y `sitemap-jobs.xml` (lastmod = fecha de publicación). `404.html` para vacantes retiradas.
- Las vacantes que el empleador retira desaparecen al día siguiente; si una fuente falla, sus vacantes de ayer se conservan máximo 5 días (`MAX_KEEP_DAYS`).
