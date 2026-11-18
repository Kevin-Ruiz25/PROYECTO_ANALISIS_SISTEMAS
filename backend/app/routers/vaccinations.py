from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import alerts, models, schemas, vaccination
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api", tags=["Vacunación"], dependencies=[Depends(require_roles(*STAFF))])


def _child(db: Session, child_id: int) -> models.Child:
    child = db.get(models.Child, child_id)
    if not child:
        raise HTTPException(404, "Niño no encontrado")
    return child


@router.get("/children/{child_id}/vaccination-card", response_model=schemas.CardOut)
def vaccination_card(child_id: int, db: Session = Depends(get_db)):
    child = _child(db, child_id)
    catalog = db.scalars(select(models.Vaccine)).all()
    return vaccination.build_card(child, catalog)


@router.post("/children/{child_id}/vaccinations", response_model=schemas.VaccinationOut, status_code=201)
def register_vaccination(child_id: int, data: schemas.VaccinationCreate, background: BackgroundTasks,
                         db: Session = Depends(get_db)):
    child = _child(db, child_id)
    vaccine = db.get(models.Vaccine, data.vaccine_id)
    if not vaccine:
        raise HTTPException(422, "La vacuna indicada no existe en el catálogo")
    if data.applied_on > date.today():
        raise HTTPException(422, "La fecha de aplicación no puede ser futura")
    if data.applied_on < child.birth_date:
        raise HTTPException(422, "La fecha de aplicación no puede ser anterior al nacimiento")
    if data.next_dose_on and data.next_dose_on <= data.applied_on:
        raise HTTPException(422, "La próxima dosis debe ser posterior a la fecha de aplicación")
    if any(r.vaccine_id == vaccine.id for r in child.vaccinations):
        raise HTTPException(409, "Esta dosis ya está registrada para el niño")

    next_dose = data.next_dose_on
    if next_dose is None:
        catalog = db.scalars(select(models.Vaccine)).all()
        next_dose = vaccination.suggest_next_dose(child.birth_date, data.applied_on, vaccine, catalog)

    record = models.Vaccination(child_id=child.id, vaccine_id=vaccine.id, applied_on=data.applied_on,
                                next_dose_on=next_dose, status=models.VaccinationStatus.complete)
    db.add(record)
    db.commit()
    db.refresh(record)
    alerts.evaluate_child(db, child)
    background.add_task(alerts.dispatch_pending)
    return record


@router.delete("/vaccinations/{vaccination_id}", status_code=204)
def delete_vaccination(vaccination_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    record = db.get(models.Vaccination, vaccination_id)
    if not record:
        raise HTTPException(404, "Registro de vacunación no encontrado")
    child_id = record.child_id
    db.delete(record)
    db.commit()
    alerts.evaluate_child(db, db.get(models.Child, child_id))
    background.add_task(alerts.dispatch_pending)
