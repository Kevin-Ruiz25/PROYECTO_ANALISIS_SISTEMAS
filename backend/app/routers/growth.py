from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts, growth, models, schemas
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api", tags=["Crecimiento"], dependencies=[Depends(require_roles(*STAFF))])


@router.get("/growth/reference")
def reference(sex: models.Sex):
    """Curvas de referencia OMS (P5, P25, P50, P75, P95) para peso y talla, de 0 a 60 meses."""
    return growth.reference_curves(sex.value)


@router.get("/children/{child_id}/growth", response_model=list[schemas.GrowthOut])
def list_records(child_id: int, db: Session = Depends(get_db)):
    if not db.get(models.Child, child_id):
        raise HTTPException(404, "Niño no encontrado")
    stmt = (select(models.GrowthRecord).where(models.GrowthRecord.child_id == child_id)
            .order_by(models.GrowthRecord.measured_on))
    return db.scalars(stmt).all()


@router.post("/children/{child_id}/growth", response_model=schemas.GrowthOut, status_code=201)
def create_record(child_id: int, data: schemas.GrowthCreate, background: BackgroundTasks,
                  db: Session = Depends(get_db)):
    child = db.get(models.Child, child_id)
    if not child:
        raise HTTPException(404, "Niño no encontrado")
    if data.measured_on > date.today():
        raise HTTPException(422, "La fecha de la medición no puede ser futura")
    if data.measured_on < child.birth_date:
        raise HTTPException(422, "La fecha de la medición no puede ser anterior al nacimiento")
    calc = growth.compute_for(child.birth_date, child.sex.value, data.measured_on, data.weight_kg, data.height_cm)
    record = models.GrowthRecord(child_id=child_id, **data.model_dump(), **calc)
    db.add(record)
    db.commit()
    db.refresh(record)
    alerts.evaluate_child(db, child)
    background.add_task(alerts.dispatch_pending)
    return record


@router.delete("/growth/{record_id}", status_code=204)
def delete_record(record_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    record = db.get(models.GrowthRecord, record_id)
    if not record:
        raise HTTPException(404, "Medición no encontrada")
    child_id = record.child_id
    db.delete(record)
    db.commit()
    alerts.evaluate_child(db, db.get(models.Child, child_id))
    background.add_task(alerts.dispatch_pending)
