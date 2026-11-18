"""Envío de correos. Separado para poder cambiarlo o simularlo en pruebas."""
import logging
import smtplib
from email.message import EmailMessage

from . import config

log = logging.getLogger("sccvi.mail")


def mode() -> str:
    """'smtp' (configurado), 'console' (simulado) o 'none' (sin configurar)."""
    if config.MAIL_MODE == "console":
        return "console"
    return "smtp" if config.SMTP_HOST else "none"


def _smtp_send(msg: EmailMessage) -> None:
    if config.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
    with server:
        if config.SMTP_PORT != 465:
            server.starttls()
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(msg)


def send_email(to: str, subject: str, body: str) -> str:
    """Devuelve 'enviada' o 'simulada'. Lanza excepción si falla el envío."""
    current = mode()
    if current == "none":
        raise RuntimeError("El correo no está configurado (falta SMTP_HOST).")
    if current == "console":
        print(f"\n--- CORREO SIMULADO ---\nPara: {to}\nAsunto: {subject}\n\n{body}\n-----------------------\n", flush=True)
        return "simulada"
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    _smtp_send(msg)
    return "enviada"
