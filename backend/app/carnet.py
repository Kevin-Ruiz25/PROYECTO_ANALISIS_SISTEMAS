"""Carnet digital: token del QR, PIN, contraseñas temporales y bloqueo por intentos fallidos.

Capas de seguridad (documento del proyecto, sección 3.7):
  1) El QR contiene un enlace con un código aleatorio e imposible de adivinar (por niño).
  2) Solo un padre/tutor autorizado del niño, con sesión iniciada, puede abrirlo.
  3) Además debe escribir el PIN de 6 dígitos que le entrega el personal de salud.
El PIN se guarda cifrado (bcrypt) y solo se muestra una vez, al generarlo.
"""
import math
import secrets
import threading
import time

from . import config

MAX_ATTEMPTS = 5
LOCK_SECONDS = 15 * 60
_TEMP_ALPHABET = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sin 0/O/1/l/I

_lock = threading.Lock()
_fails: dict[tuple[int, int], list[float]] = {}  # (usuario, niño) -> [fallos, bloqueado_hasta]


def new_token() -> str:
    return secrets.token_urlsafe(24)


def new_pin() -> str:
    return f"{secrets.randbelow(10 ** 6):06d}"


def temp_password(length: int = 10) -> str:
    return "".join(secrets.choice(_TEMP_ALPHABET) for _ in range(length))


def carnet_url(token: str) -> str:
    return f"{config.PUBLIC_BASE_URL.rstrip('/')}/carnet/{token}"


def qr_data_uri(url: str) -> str:
    try:
        import segno
    except ModuleNotFoundError as exc:  # el resto del sistema debe seguir funcionando
        raise RuntimeError("Falta la librería del QR. En la terminal del backend ejecuta: "
                           "pip install -r requirements.txt  y reinicia el servidor.") from exc
    return segno.make(url, error="m").svg_data_uri(scale=6, border=2, dark="#17323a", light="#ffffff")


# ---- Bloqueo por intentos (en memoria: válido para un solo proceso del backend)
def locked_minutes(user_id: int, child_id: int, now: float | None = None) -> int:
    """Minutos que faltan para poder reintentar; 0 si no está bloqueado."""
    now = now or time.time()
    with _lock:
        entry = _fails.get((user_id, child_id))
        if entry and entry[1] > now:
            return max(1, math.ceil((entry[1] - now) / 60))
        if entry and entry[1] and entry[1] <= now:
            del _fails[(user_id, child_id)]  # el bloqueo ya venció
    return 0


def register_failure(user_id: int, child_id: int, now: float | None = None) -> int:
    """Cuenta un fallo y devuelve cuántos intentos quedan (0 = quedó bloqueado)."""
    now = now or time.time()
    with _lock:
        entry = _fails.setdefault((user_id, child_id), [0, 0.0])
        entry[0] += 1
        if entry[0] >= MAX_ATTEMPTS:
            entry[1] = now + LOCK_SECONDS
            return 0
        return MAX_ATTEMPTS - entry[0]


def register_success(user_id: int, child_id: int) -> None:
    with _lock:
        _fails.pop((user_id, child_id), None)


def reset_child(child_id: int) -> None:
    """Desbloquea a todos los padres de un niño (al emitir un PIN nuevo)."""
    with _lock:
        for key in [k for k in _fails if k[1] == child_id]:
            del _fails[key]


def reset_all() -> None:
    with _lock:
        _fails.clear()
