from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts, exports, models, reports
from ..database import get_db
from ..deps import CATALOG_ADMIN, require_roles

# Reportes y campañas: solo para el encargado del centro y administradores
router = APIRouter(prefix="/api", tags=["Reportes y campañas"])
manager_only = require_roles(*CATALOG_ADMIN)


def _check(kind: str):
    if kind not in reports.KINDS:
        raise HTTPException(404, f"Reporte desconocido. Opciones: {', '.join(reports.KINDS)}")


def _community_name(db: Session, community_id: int | None) -> str | None:
    if not community_id:
        return None
    c = db.get(models.Community, community_id)
    if not c:
        raise HTTPException(404, "Comunidad no encontrada")
    return c.name


@router.get("/reports/summary")
def report_summary(community_id: int | None = None, db: Session = Depends(get_db), _=Depends(manager_only)):
    _community_name(db, community_id)
    snaps = reports.snapshots(db, community_id=community_id)
    return {"generated_on": date.today(), **reports.summary(snaps)}


@router.get("/reports/{kind}")
def get_report(kind: str, community_id: int | None = None, db: Session = Depends(get_db), _=Depends(manager_only)):
    _check(kind)
    _community_name(db, community_id)
    cid = None if kind in reports.UNFILTERED else community_id
    return {"kind": kind, "generated_on": date.today(), **reports.build(kind, reports.snapshots(db, community_id=cid))}


@router.get("/reports/{kind}/export")
def export_report(kind: str, format: str = Query("xlsx", pattern="^(xlsx|pdf)$"), community_id: int | None = None,
                  db: Session = Depends(get_db), user: models.User = Depends(manager_only)):
    _check(kind)
    name = _community_name(db, community_id)
    cid = None if kind in reports.UNFILTERED else community_id
    report = reports.build(kind, reports.snapshots(db, community_id=cid))
    subtitle = exports.stamp(name if cid else None, user.full_name)
    if format == "pdf":
        data, media = exports.to_pdf(report, subtitle), "application/pdf"
    else:
        data, media = exports.to_xlsx(report, subtitle), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    filename = f"sccvi-{kind}-{date.today().isoformat()}.{format}"
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ------------------------------------------------------------------ campañas
class CampaignFilter(BaseModel):
    community_ids: list[int] = []
    age_min_months: int = Field(0, ge=0, le=216)
    age_max_months: int = Field(60, ge=0, le=216)
    vaccination: str = Field("con_pendientes", pattern="^(todos|con_pendientes|atrasadas|al_dia)$")
    vaccine_name: str | None = None


class CampaignSend(CampaignFilter):
    title: str = Field(min_length=3, max_length=120)
    message: str = Field(min_length=10, max_length=1500)
    event_date: date | None = None
    place: str | None = Field(None, max_length=200)


MAX_RECIPIENTS = 2000


def _targets(db: Session, f: CampaignFilter):
    if f.age_min_months > f.age_max_months:
        raise HTTPException(422, "La edad mínima no puede ser mayor que la máxima")
    snaps = reports.snapshots(db)
    return reports.campaign_targets(snaps, f.community_ids, f.age_min_months, f.age_max_months,
                                    f.vaccination, f.vaccine_name or None)


@router.get("/campaigns/vaccine-names")
def vaccine_names(db: Session = Depends(get_db), _=Depends(manager_only)):
    names = db.scalars(select(models.Vaccine.name).distinct().order_by(models.Vaccine.name)).all()
    return list(names)


@router.post("/campaigns/preview")
def campaign_preview(f: CampaignFilter, db: Session = Depends(get_db), _=Depends(manager_only)):
    """Cuántos niños y padres alcanzaría la campaña, sin enviar nada."""
    targets = _targets(db, f)
    recips = reports.campaign_recipients(targets)
    with_email = sum(1 for r in recips.values() if r["parent"].email)
    return {
        "children": len(targets), "parents": len(recips), "with_email": with_email,
        "without_contact": len(recips) - with_email,
        "children_without_parents": sum(1 for s in targets if not s["parents"]),
        "sample": [{"child_id": s["child_id"], "name": s["name"], "age_months": s["age_months"],
                    "community": s["community"], "doses_overdue": s["doses_overdue"],
                    "doses_pending": s["doses_pending"]} for s in targets[:50]],
    }


@router.post("/campaigns/send")
def campaign_send(data: CampaignSend, db: Session = Depends(get_db), _=Depends(manager_only)):
    """Crea un aviso por cada padre/tutor (uno solo aunque tenga varios niños) y lo envía por correo."""
    targets = _targets(db, data)
    recips = reports.campaign_recipients(targets)
    if not recips:
        raise HTTPException(422, "Con estos filtros no hay padres o tutores a quienes avisar")
    if len(recips) > MAX_RECIPIENTS:
        raise HTTPException(422, f"La campaña alcanza a {len(recips)} padres; el máximo por envío es {MAX_RECIPIENTS}. "
                                 "Acota por comunidad o por edad.")
    details = []
    if data.event_date:
        details.append(f"Fecha: {data.event_date.strftime('%d/%m/%Y')}")
    if data.place:
        details.append(f"Lugar: {data.place}")
    created = skipped = 0
    for entry in recips.values():
        parent = entry["parent"]
        if parent.email:
            channel, status = models.Channel.email, "pendiente"
        elif parent.preferred_channel == models.Channel.email:
            channel, status = models.Channel.email, "sin_contacto"
        else:
            channel, status = parent.preferred_channel, "canal_no_disponible"
        kids = ", ".join(entry["children"])
        body = "\n\n".join(filter(None, [
            f"Hola {parent.full_name},", data.message.strip(),
            f"Niños incluidos: {kids}.", "\n".join(details) or None,
            "Este es un mensaje del Sistema de Control de Crecimiento y Vacunación Infantil."]))
        db.add(models.Notification(parent_id=parent.id, alert_id=None, channel=channel, status=status,
                                   subject=f"SCCVI: {data.title}", body=body))
        created += 1
        if status != "pendiente":
            skipped += 1
    db.commit()
    sent = alerts.dispatch_pending(db)
    return {"children": len(targets), "parents": len(recips), "created": created,
            "without_contact": skipped, "envio": sent}
