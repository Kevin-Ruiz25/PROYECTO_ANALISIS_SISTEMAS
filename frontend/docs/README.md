# Documentación del SCCVI

| Archivo | Contenido |
|---|---|
| `SCCVI-Documentacion-Tecnica.docx` | Documento completo: arquitectura, UML, reglas de negocio, API, seguridad, instalación |
| `openapi.json` | Especificación OpenAPI (la misma que muestra Swagger) |
| `diagramas/*.mmd` | Fuente de cada diagrama (Mermaid, editable como texto) |
| `diagramas/*.png`, `*.svg` | Diagramas listos para insertar en informes |

Diagramas: 01 casos de uso · 02 clases · 03 componentes · 04 secuencia de medición y alerta · 05 secuencia del carnet QR ·
06 secuencia de campaña · 07 secuencia de vinculación de Telegram · 08 reglas de alertas.

## Swagger
Con el backend en ejecución: <http://localhost:8000/docs> (probar endpoints) y <http://localhost:8000/redoc> (lectura).
Para regenerar `openapi.json` desde `backend`: `python -m app.export_openapi`.

## Editar un diagrama
Modifica el `.mmd` y vuelve a generarlo con Mermaid CLI: `mmdc -i diagramas/02-clases.mmd -o diagramas/02-clases.png -s 2 -b white`
(o pega el texto en <https://mermaid.live>).
