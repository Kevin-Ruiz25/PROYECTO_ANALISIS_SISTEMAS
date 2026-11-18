import os
from pathlib import Path


def _read_text(path: Path) -> str:
    """Lee el .env sin importar cómo lo guardó el editor (UTF-8, con BOM, UTF-16 o ANSI de Windows)."""
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _load_dotenv() -> None:
    """Lee backend/.env si existe (así no hace falta exportar variables, también en Windows)."""
    path = Path(__file__).resolve().parent.parent / ".env"
    if not path.exists():
        return
    try:
        text = _read_text(path)
    except Exception as exc:  # noqa: BLE001 - un .env dañado no debe impedir que el servidor arranque
        print(f"AVISO: no se pudo leer {path}: {exc}. Se usan los valores por defecto.", flush=True)
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./sccvi.db")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-cambiar-en-produccion")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
ALGORITHM = "HS256"

# --- Correo (alertas a padres)
# MAIL_MODE=smtp    -> envía de verdad (requiere SMTP_HOST)
# MAIL_MODE=console -> no envía: imprime el correo en la terminal del backend (para demostraciones)
MAIL_MODE = os.getenv("MAIL_MODE", "smtp").lower()
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or os.getenv("SMTP_USER", "")

# Cada cuántas horas se revisan todos los niños automáticamente (0 = desactivado)
ALERT_CHECK_HOURS = float(os.getenv("ALERT_CHECK_HOURS", "24"))

# --- Carnet digital: dirección pública del frontend que se codifica dentro del QR.
# Para escanearlo desde un celular en la misma red, usa la IP de tu computadora (p. ej. http://192.168.1.20:5173).
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5173")
