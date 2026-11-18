
reportes y campañas (rol Encargado del centro / Administrador)

Instalar las dependencias nuevas en el backend: `pip install -r requirements.txt` (openpyxl y reportlab).

- **Reportes** (`/reportes`): niños con bajo peso (P<5), sobrepeso (P>95), vacunas incompletas, cobertura de vacunación por comunidad y crecimiento promedio por comunidad y por edad. Se descargan en Excel y PDF.
- **Campañas** (`/campanas`): selecciona comunidades, rango de edad, estado de vacunación (y opcionalmente una vacuna) y envía un aviso por correo. Cada padre recibe un solo mensaje aunque tenga varios niños; los que no tienen correo quedan registrados como «sin contacto».
- API: `GET /api/reports/summary`, `GET /api/reports/{kind}`, `GET /api/reports/{kind}/export?format=xlsx|pdf`, `POST /api/campaigns/preview`, `POST /api/campaigns/send`.
