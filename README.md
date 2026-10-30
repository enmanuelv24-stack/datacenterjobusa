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

## Agregar una empresa

- Si usa Greenhouse: agrega `"nombre-del-board": "Empresa"` en `GREENHOUSE_BOARDS` dentro de `collector.py`.
- Si usa Ashby: igual, en `ASHBY_ORGS`.
- Si usa Workday: agrega una línea en `WORKDAY_SITES` con `(empresa, host, tenant, sitio)`, tomados de la dirección de su página de empleos.

Nunca agregues Indeed, LinkedIn ni otros agregadores: sus términos lo prohíben.

## Después de publicar

1. Da de alta el sitio en Google Search Console y envía `sitemap.xml`.
2. Conecta el formulario de suscripción a un servicio de newsletter (beehiiv, Buttondown o Kit). El formulario de hoy es de muestra y no guarda correos.
3. Pon el enlace de tu encuesta de turnos en `SURVEY_URL` dentro de `site_config.py`.
