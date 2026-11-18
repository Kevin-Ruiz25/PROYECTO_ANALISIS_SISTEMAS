from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts, mailer, models, schemas
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api", tags=["Alertas"], dependencies=[Depends(require_roles(*STAFF))])


def _alert_out(a: models.Alert) -> dict:
    return {
        "id": a.id, "child_id": a.child_id, "child_name": a.child.full_name,
        "community_name": a.child.community.name if a.child.community else None,
        "type": a.type.value, "reason": a.reason, "message": a.message,
        "created_at": a.created_at, "resolved": a.resolved,
    }


@router.get("/alerts", response_model=list[schemas.AlertOut])
def list_alerts(status: str = "open", type: str | None = None, child_id: int | None = None,
                limit: int = 500, db: Session = Depends(get_db)):
    """status: open | resolved | all. Las críticas aparecen primero."""
    if status not in ("open", "resolved", "all"):
        raise HTTPException(422, "status debe ser open, resolved o all")
    stmt = select(models.Alert)
    if status == "open":
        stmt = stmt.where(models.Alert.resolved.is_(False))
    elif status == "resolved":
        stmt = stmt.where(models.Alert.resolved.is_(True))
    if child_id:
        stmt = stmt.where(models.Alert.child_id == child_id)
    rows = db.scalars(stmt.order_by(models.Alert.created_at.desc()).limit(min(limit, 1000))).all()
    if type:
        rows = [a for a in rows if a.type.value == type]
    rows.sort(key=lambda a: a.type != models.AlertType.critical)  # estable: críticas primero, luego más recientes
    return [_alert_out(a) for a in rows]


@router.post("/alerts/evaluate")
def evaluate_all(db: Session = Depends(get_db)):
    """Revisa todos los niños, abre/cierra alertas y envía las notificaciones por correo."""
    result = alerts.evaluate_all(db)
    result["envio"] = alerts.dispatch_pending(db)
    return result


@router.get("/notifications", response_model=list[schemas.NotificationOut])
def list_notifications(limit: int = 200, db: Session = Depends(get_db)):
    rows = db.scalars(select(models.Notification).order_by(models.Notification.id.desc())
                      .limit(min(limit, 1000))).all()
    out = []
    for n in rows:
        parent = db.get(models.Parent, n.parent_id)
        alert = db.get(models.Alert, n.alert_id) if n.alert_id else None
        out.append({
            "id": n.id, "parent_id": n.parent_id, "parent_name": parent.full_name if parent else "—",
            "child_id": alert.child_id if alert else None,
            "child_name": alert.child.full_name if alert else None,
            "alert_id": n.alert_id, "channel": n.channel.value, "subject": n.subject,
            "status": n.status, "sent_at": n.sent_at,
        })
    return out


@router.post("/notifications/dispatch")
def dispatch(db: Session = Depends(get_db)):
    """Reintenta el envío de las notificaciones pendientes o con error."""
    return alerts.dispatch_pending(db)


@router.get("/mail/status")
def mail_status():
    """'smtp' = envío real, 'console' = simulado en la terminal del backend, 'none' = sin configurar."""
    return {"mode": mailer.mode()}
