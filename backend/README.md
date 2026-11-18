
## Paso 7: reportes y campañas (rol Encargado del centro / Administrador)

Instalar las dependencias nuevas en el backend: `pip install -r requirements.txt` (openpyxl y reportlab).

- **Reportes** (`/reportes`): niños con bajo peso (P<5), sobrepeso (P>95), vacunas incompletas, cobertura de vacunación por comunidad y crecimiento promedio por comunidad y por edad. Se descargan en Excel y PDF.
- **Campañas** (`/campanas`): selecciona comunidades, rango de edad, estado de vacunación (y opcionalmente una vacuna) y envía un aviso por correo. Cada padre recibe un solo mensaje aunque tenga varios niños; los que no tienen correo quedan registrados como «sin contacto».
- API: `GET /api/reports/summary`, `GET /api/reports/{kind}`, `GET /api/reports/{kind}/export?format=xlsx|pdf`, `POST /api/campaigns/preview`, `POST /api/campaigns/send`.

## Paso 8: Telegram y WhatsApp

- Cada padre recibe los avisos por el canal que prefiere (correo, Telegram o WhatsApp). Si ese canal no está disponible
  (no vinculó Telegram, no hay teléfono, el canal no está configurado), se usa el siguiente que tenga.
- **Telegram**: crea un bot con @BotFather, pon `TELEGRAM_BOT_TOKEN` en `backend/.env` y reinicia. En «Padres de familia» →
  «Vincular» se genera un enlace de un solo uso que el padre abre en su celular.
- **WhatsApp**: requiere la Cloud API de Meta (`WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`) y una plantilla aprobada
  (`WHATSAPP_TEMPLATE`) con una variable en el cuerpo.
- Para probar sin cuentas reales: `TELEGRAM_MODE=console` y `WHATSAPP_MODE=console` imprimen los mensajes en la terminal.
- La base de datos existente se actualiza sola al arrancar (dos columnas nuevas en `parents`); no se pierden datos.
