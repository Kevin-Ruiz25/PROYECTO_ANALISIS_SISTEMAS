# Guía de despliegue del SCCVI

El sistema se publica con **Docker Compose**: tres contenedores (base de datos PostgreSQL, backend FastAPI y un servidor
web Caddy que sirve el frontend y consigue el certificado HTTPS solo).

```
Internet ──► Caddy (80/443, HTTPS) ──┬─► archivos del frontend (React)
                                     └─► /api/*  ──► backend (FastAPI) ──► PostgreSQL (volumen pgdata)
```

> Los archivos Docker se escribieron y se revisaron aquí, pero las imágenes no se construyeron en el entorno donde se
> preparó el proyecto. Haz primero la **prueba local** (sección 1): si algo falla, aparece ahí y no en el servidor real.
> Sí se probó el backend contra PostgreSQL 16 real (47 pruebas), la validación de configuración y el respaldo/restauración.

## 1. Prueba local con Docker Desktop (recomendado antes de publicar)

1. Instala **Docker Desktop** (Windows/Mac) y ábrelo hasta que diga «running».
2. En la carpeta del proyecto (donde está `docker-compose.yml`) copia el archivo de ejemplo:
   ```powershell
   copy .env.production.example .env
   ```
3. Edita `.env` con el Bloc de notas y completa **como mínimo**:
   - `POSTGRES_PASSWORD`: una clave inventada, solo letras y números.
   - `SECRET_KEY`: 64 caracteres al azar. En PowerShell: `-join ((48..57)+(97..122) | Get-Random -Count 64 | % {[char]$_})`
   - `ADMIN_PASSWORD`: tu contraseña de administrador (10 o más caracteres) y `ADMIN_EMAIL` (un correo con dominio válido, como `admin@tucentro.gt`; no uses `.local`).
   - Deja `DOMAIN=:80` y `PUBLIC_BASE_URL=http://localhost`.
   > Guarda el archivo como **UTF-8**. No lo crees con `echo ... > .env` en PowerShell (queda en UTF-16).
4. Arranca todo:
   ```powershell
   docker compose up -d --build
   ```
   La primera vez tarda varios minutos (descarga e instala).
5. Abre http://localhost e inicia sesión con `ADMIN_EMAIL` y `ADMIN_PASSWORD`.
6. Si algo falla: `docker compose logs backend` (o `web`, `db`). Para apagar: `docker compose down` (los datos se conservan).

## 2. Publicar en un servidor real

### 2.1 Lo que necesitas
- Un **servidor Linux** (Ubuntu 22.04 o 24.04) con al menos 1 GB de RAM y 10 GB de disco. Un VPS pequeño de cualquier proveedor
  suele ser suficiente para un centro de salud.
- Un **dominio** (o subdominio) para tener HTTPS, por ejemplo `sccvi.midominio.com`. Los avisos con QR y los datos de salud de
  menores no deben viajar sin HTTPS.
- Los puertos **80 y 443** abiertos en el firewall del proveedor.

### 2.2 Pasos
1. **DNS**: crea un registro `A` de tu dominio hacia la IP pública del servidor y espera unos minutos.
2. **Instala Docker** en el servidor (conectado por SSH):
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. **Sube el proyecto** (desde tu computadora, en la carpeta que contiene `sccvi`):
   ```bash
   scp -r sccvi usuario@IP_DEL_SERVIDOR:~/
   ```
   (No subas `.venv` ni `node_modules`; el zip del proyecto ya no los trae.)
4. **Configura** en el servidor:
   ```bash
   cd ~/sccvi
   cp .env.production.example .env
   nano .env
   ```
   Completa lo mismo que en la prueba local, pero con:
   ```
   DOMAIN=sccvi.midominio.com
   PUBLIC_BASE_URL=https://sccvi.midominio.com
   ```
   Genera claves con `openssl rand -hex 32` (para `SECRET_KEY`) y `openssl rand -hex 16` (para `POSTGRES_PASSWORD`).
   Protege el archivo: `chmod 600 .env`.
5. **Arranca**:
   ```bash
   docker compose up -d --build
   docker compose ps
   docker compose logs -f web      # espera "certificate obtained successfully"
   ```
6. Abre `https://sccvi.midominio.com`, entra con el administrador y **crea los usuarios** del personal.

### 2.3 Correo, Telegram y WhatsApp
Se configuran en el mismo `.env` (variables `SMTP_*`, `TELEGRAM_BOT_TOKEN`, `WHATSAPP_*`). Después de cambiar el `.env`:
```bash
docker compose up -d
```
El detalle de cada canal está en `backend/.env.example`. Recuerda que WhatsApp necesita una plantilla aprobada por Meta.

## 3. Operación diaria

| Tarea | Comando |
|---|---|
| Ver estado | `docker compose ps` |
| Ver registros | `docker compose logs -f backend` |
| Reiniciar | `docker compose restart` |
| Actualizar a una versión nueva | reemplaza los archivos y ejecuta `docker compose up -d --build` |
| Apagar (conserva datos) | `docker compose down` |

> **Nunca** uses `docker compose down -v`: el `-v` borra los volúmenes, es decir, **la base de datos y los certificados**.

Las tablas nuevas o columnas nuevas se agregan solas al arrancar una versión actualizada.

## 4. Copias de seguridad

```bash
./deploy/backup.sh                                   # crea backups/sccvi-FECHA.sql.gz (conserva las últimas 14)
./deploy/restore.sh backups/sccvi-2026-11-15_0300.sql.gz   # restaura (pide confirmar; reemplaza los datos)
```

Programa una copia diaria con `crontab -e` (ejemplo, todos los días a las 3:00):
```
0 3 * * * cd /home/usuario/sccvi && ./deploy/backup.sh >> backups/backup.log 2>&1
```
**Una copia que está solo en el mismo servidor no te salva si el servidor se pierde.** Copia la carpeta `backups/` a otro lugar
con regularidad (por ejemplo, `scp` a tu computadora o el almacenamiento de tu proveedor). Prueba restaurar al menos una vez
en una prueba local para saber que funciona.

## 5. Lista de seguridad antes de abrir al público
- [ ] `SECRET_KEY` y `POSTGRES_PASSWORD` propios y largos (el backend se niega a arrancar en producción con la clave por defecto).
- [ ] Contraseña del administrador cambiada y usuarios del personal con contraseñas propias.
- [ ] Sitio abierto solo por `https://`.
- [ ] Firewall: solo 22 (SSH), 80 y 443. **No** abras el puerto 5432 de la base de datos (en este compose no se publica).
- [ ] `.env` fuera de GitHub y con permisos `600`.
- [ ] Copias diarias programadas y una copia fuera del servidor.
- [ ] Servidor actualizado (`sudo apt update && sudo apt upgrade`) y acceso SSH con llave.
- [ ] Opcional: `ENABLE_DOCS=false` para ocultar Swagger al público.
- [ ] Se informó a los padres y se cuenta con su consentimiento para registrar datos de salud de sus hijos, según la normativa del centro.

## 6. Problemas frecuentes

| Síntoma | Causa probable y solución |
|---|---|
| `backend` se reinicia y los registros dicen «Configuración insegura para producción» | Falta `SECRET_KEY`, `ADMIN_PASSWORD` o son los valores por defecto. Corrige el `.env` y `docker compose up -d`. |
| Caddy no obtiene el certificado | El DNS aún no apunta al servidor, o los puertos 80/443 están cerrados. Revisa `docker compose logs web`. |
| «Falta POSTGRES_PASSWORD en el archivo .env» | No existe el `.env` o está vacío ese valor. |
| Cambié `ADMIN_PASSWORD` y no sirve | Solo se usa la primera vez (base vacía). Cámbiala desde «Cambiar contraseña» en el sistema. |
| El QR abre una dirección con `localhost` | `PUBLIC_BASE_URL` no es la dirección pública. Corrígela y reinicia; los QR ya impresos conservan la anterior. |
| Telegram no vincula | Revisa `TELEGRAM_BOT_TOKEN` y que el servidor tenga salida a internet. |

## 7. Notas de diseño
- El backend corre con **un solo proceso**: la revisión periódica de alertas, el sondeo de Telegram y el bloqueo por PIN están en
  memoria. Para más capacidad aumenta los recursos del servidor.
- Alternativas sin Docker (Render, Railway, etc.) son posibles: backend como servicio web con PostgreSQL administrado y el
  frontend compilado (`npm run build`) detrás de una regla que reenvíe `/api/*` al backend. No se probaron aquí.
