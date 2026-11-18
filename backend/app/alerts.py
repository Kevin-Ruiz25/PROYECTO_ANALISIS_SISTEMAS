"""Motor de alertas: evalúa reglas de negocio, abre/cierra alertas y genera notificaciones.

Reglas (documento del proyecto):
  - Percentil de peso < 5   -> crítica  (posible desnutrición)
  - Percentil de peso > 95  -> preventiva (posible sobrepeso)
  - Sin controles recientes -> preventiva. Frecuencia recomendada: 0-2 años mensual,
    2-5 años trimestral; se alerta al pasar ~1 mes de margen.
  - Vacunas atrasadas       -> preventiva; crítica si son 3 o más dosis.

Una alerta está "abierta" mientras la condición se cumple y se cierra sola cuando deja de cumplirse
(por ejemplo, al registrar un nuevo control o aplicar la vacuna). No se duplican alertas abiertas.
"""
import logging
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import growth, mailer, models, vaccination
from .database import SessionLocal

log = logging.getLogger("sccvi.alerts")

LOW_PERCENTILE = 5
HIGH_PERCENTILE = 95
MONTHLY_LIMIT_DAYS = 61      # 0-2 años: control mensual + ~1 mes de margen
QUARTERLY_LIMIT_DAYS = 122   # 2-5 años: control trimestral + ~1 mes de margen
CRITICAL_OVERDUE_DOSES = 3
MAX_GROWTH_AGE_MONTHS = 60

REASONS = {
    "peso_bajo": "Peso bajo",
    "peso_alto": "Peso alto",
    "sin_controles": "Sin controles",
    "vacunas_atrasadas": "Vacunas atrasadas",
}


def _who(child) -> str:
    return f"{'La niña' if child.sex == models.Sex.F else 'El niño'} {child.full_name}"


def _months_since(d: date, today: date) -> int:
    return max(1, round((today - d).days / 30.4375))


def _conditions(child, catalog, today: date) -> dict[str, tuple[models.AlertType, str]]:
    """Condiciones que se cumplen hoy: {motivo: (tipo, mensaje)}."""
    found: dict[str, tuple[models.AlertType, str]] = {}
    who = _who(child)
    records = sorted(child.growth_records, key=lambda r: r.measured_on)

    # 1) Percentil de peso (último control)
    if records and records[-1].weight_percentile is not None:
        p = records[-1].weight_percentile
        if p < LOW_PERCENTILE:
            found["peso_bajo"] = (models.AlertType.critical,
                                  f"{who} presenta peso bajo para su edad. Se recomienda acudir al centro de salud.")
        elif p > HIGH_PERCENTILE:
            found["peso_alto"] = (models.AlertType.preventive,
                                  f"{who} presenta peso alto para su edad. Se recomienda acudir al centro de salud "
                                  f"para una evaluación.")

    # 2) Controles al día
    age = growth.age_in_months(child.birth_date, today)
    if 0 <= age <= MAX_GROWTH_AGE_MONTHS:
        limit = MONTHLY_LIMIT_DAYS if age < 24 else QUARTERLY_LIMIT_DAYS
        if records:
            last = records[-1].measured_on
            if (today - last).days > limit:
                found["sin_controles"] = (models.AlertType.preventive,
                                          f"{who} no tiene control de peso y talla desde hace "
                                          f"{_months_since(last, today)} meses. Se recomienda acudir al centro de salud.")
        elif (today - child.birth_date).days > 30:
            found["sin_controles"] = (models.AlertType.preventive,
                                      f"{who} no tiene controles de peso y talla registrados. "
                                      f"Se recomienda acudir al centro de salud.")

    # 3) Vacunas atrasadas
    card = vaccination.build_card(child, catalog, today)
    overdue = [i for i in card["items"] if i["status"] == "atrasada"]
    if overdue:
        names = [f"{i['vaccine'].name} (dosis {i['vaccine'].dose_number})" for i in overdue[:3]]
        extra = f" y {len(overdue) - 3} más" if len(overdue) > 3 else ""
        kind = models.AlertType.critical if len(overdue) >= CRITICAL_OVERDUE_DOSES else models.AlertType.preventive
        found["vacunas_atrasadas"] = (kind,
                                      f"{who} tiene {len(overdue)} dosis de vacunas atrasadas: {', '.join(names)}{extra}. "
                                      f"Se recomienda acudir al centro de salud para completar su esquema.")
    return found


def _notify(db: Session, child, alert: models.Alert) -> int:
    """Crea una notificación por cada padre/tutor. Devuelve cuántas creó."""
    kind = "crítica" if alert.type == models.AlertType.critical else "preventiva"
    n = 0
    for parent in child.parents:
        if parent.email:
            channel, status = models.Channel.email, "pendiente"
        elif parent.preferred_channel == models.Channel.email:
            channel, status = models.Channel.email, "sin_contacto"       # prefiere correo pero no lo registró
        else:
            channel, status = parent.preferred_channel, "canal_no_disponible"  # Telegram/WhatsApp: aún sin integrar
        db.add(models.Notification(
            parent_id=parent.id, alert_id=alert.id, channel=channel, status=status,
            subject=f"SCCVI: alerta {kind} para {child.full_name}",
            body=(f"Hola {parent.full_name},\n\n{alert.message}\n\n"
                  "Este es un mensaje automático del Sistema de Control de Crecimiento y Vacunación Infantil."),
        ))
        n += 1
    return n


def evaluate_child(db: Session, child, today: date | None = None) -> dict:
    """Abre alertas nuevas, cierra las que ya no aplican y crea notificaciones. Hace commit."""
    today = today or date.today()
    catalog = db.scalars(select(models.Vaccine)).all()
    now = _conditions(child, catalog, today)
    open_alerts = {a.reason: a for a in db.scalars(
        select(models.Alert).where(models.Alert.child_id == child.id, models.Alert.resolved.is_(False)))}
    result = {"created": 0, "resolved": 0, "notifications": 0}

    for reason, alert in open_alerts.items():
        if reason not in now:
            alert.resolved = True
            result["resolved"] += 1

    for reason, (kind, message) in now.items():
        existing = open_alerts.get(reason)
        if existing is None:
            alert = models.Alert(child_id=child.id, type=kind, reason=reason, message=message)
            db.add(alert)
            db.flush()
            result["created"] += 1
            result["notifications"] += _notify(db, child, alert)
        else:
            escalated = existing.type != kind and kind == models.AlertType.critical
            existing.type, existing.message = kind, message
            if escalated:  # pasó de preventiva a crítica: se vuelve a avisar
                result["notifications"] += _notify(db, child, existing)
    db.commit()
    return result


def evaluate_all(db: Session, today: date | None = None) -> dict:
    total = {"children": 0, "created": 0, "resolved": 0, "notifications": 0}
    for child in db.scalars(select(models.Child)).all():
        r = evaluate_child(db, child, today)
        total["children"] += 1
        for k in ("created", "resolved", "notifications"):
            total[k] += r[k]
    return total


def dispatch_pending(db: Session | None = None) -> dict:
    """Envía las notificaciones por correo pendientes (o que fallaron). Seguro de llamar en segundo plano."""
    own = db is None
    db = db or SessionLocal()
    stats = {"enviadas": 0, "simuladas": 0, "errores": 0, "pendientes": 0, "ultimo_error": None}
    try:
        rows = db.scalars(select(models.Notification).where(
            models.Notification.status.in_(["pendiente", "error"]),
            models.Notification.channel == models.Channel.email)).all()
        if rows and mailer.mode() == "none":
            stats["pendientes"] = len(rows)
            return stats
        for n in rows:
            parent = db.get(models.Parent, n.parent_id)
            if not parent or not parent.email:
                n.status = "sin_contacto"
                continue
            try:
                outcome = mailer.send_email(parent.email, n.subject, n.body)
                n.status, n.sent_at = outcome, datetime.utcnow()
                stats["enviadas" if outcome == "enviada" else "simuladas"] += 1
            except Exception as exc:  # noqa: BLE001 - cualquier fallo de red/SMTP
                n.status = "error"
                stats["errores"] += 1
                stats["ultimo_error"] = str(exc)
                log.warning("No se pudo enviar correo a notificación %s: %s", n.id, exc)
        db.commit()
        return stats
    finally:
        if own:
            db.close()


def run_scheduled_check() -> None:
    """Revisión periódica (las condiciones por tiempo, como 'sin controles', cambian solas)."""
    with SessionLocal() as db:
        res = evaluate_all(db)
        log.info("Revisión automática de alertas: %s", res)
    dispatch_pending()
