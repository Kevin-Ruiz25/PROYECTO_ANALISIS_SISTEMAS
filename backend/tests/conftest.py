import os

# Base de datos limpia para cada ejecución de pruebas
if os.path.exists("test.db"):
    os.remove("test.db")
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["ALERT_CHECK_HOURS"] = "0"   # sin tarea periódica en pruebas
os.environ["MAIL_MODE"] = "smtp"
os.environ["SMTP_HOST"] = ""            # sin correo real: cada prueba lo simula
