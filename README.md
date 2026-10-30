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

## Publicarlo gratis (una sola vez, unos 20 minutos)

1. Crea una cuenta en GitHub (gratis) y un repositorio nuevo, por ejemplo `datacenterjobusa`.
2. Sube todos estos archivos al repositorio (botón "Add file > Upload files", arrastra la carpeta).
3. En el repositorio: **Settings > Pages > Source: GitHub Actions**.
4. En **Actions**, abre "Actualizar sitio" y pulsa **Run workflow**. En unos minutos el sitio queda en
   `https://TU-USUARIO.github.io/datacenterjobusa/`.
5. Desde ese momento se actualiza solo todos los días a las 6:17 am hora de Texas.

## Conectar tu dominio

1. Compra el dominio (Cloudflare Registrar, Namecheap o Porkbun; unos $10–$15 al año para un .com).
2. En GitHub: **Settings > Pages > Custom domain**, escribe el dominio y guarda.
3. En tu registrador, crea los registros DNS que GitHub te indica.
4. Cambia `SITE_URL` en `site_config.py` por tu dominio.

## Agregar una empresa

- Si usa Greenhouse: agrega `"nombre-del-board": "Empresa"` en `GREENHOUSE_BOARDS` dentro de `collector.py`.
- Si usa Ashby: igual, en `ASHBY_ORGS`.
- Si usa Workday: agrega una línea en `WORKDAY_SITES` con `(empresa, host, tenant, sitio)`, tomados de la dirección de su página de empleos.

Nunca agregues Indeed, LinkedIn ni otros agregadores: sus términos lo prohíben.

## Después de publicar

1. Da de alta el sitio en Google Search Console y envía `sitemap.xml`.
2. Conecta el formulario de suscripción a un servicio de newsletter (beehiiv, Buttondown o Kit). El formulario de hoy es de muestra y no guarda correos.
3. Pon el enlace de tu encuesta de turnos en `SURVEY_URL` dentro de `site_config.py`.
