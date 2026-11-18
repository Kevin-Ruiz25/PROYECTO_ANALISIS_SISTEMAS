from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import CATALOG_ADMIN, STAFF, require_roles

router = APIRouter(prefix="/api/vaccines", tags=["Catálogo de vacunas"])
can_edit = Depends(require_roles(*CATALOG_ADMIN))


def _duplicate(db: Session, name: str, dose: int, exclude_id: int | None = None) -> bool:
    stmt = select(models.Vaccine).where(models.Vaccine.name == name, models.Vaccine.dose_number == dose)
    found = db.scalar(stmt)
    return bool(found and found.id != exclude_id)


@router.get("", response_model=list[schemas.VaccineOut], dependencies=[Depends(require_roles(*STAFF))])
def list_vaccines(db: Session = Depends(get_db)):
    stmt = select(models.Vaccine).order_by(models.Vaccine.recommended_age_months, models.Vaccine.name,
                                           models.Vaccine.dose_number)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.VaccineOut, status_code=201, dependencies=[can_edit])
def create_vaccine(data: schemas.VaccineCreate, db: Session = Depends(get_db)):
    if _duplicate(db, data.name, data.dose_number):
        raise HTTPException(409, "Ya existe esa vacuna con ese número de dosis")
    obj = models.Vaccine(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{vaccine_id}", response_model=schemas.VaccineOut, dependencies=[can_edit])
def update_vaccine(vaccine_id: int, data: schemas.VaccineCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Vaccine, vaccine_id)
    if not obj:
        raise HTTPException(404, "Vacuna no encontrada")
    if _duplicate(db, data.name, data.dose_number, exclude_id=vaccine_id):
        raise HTTPException(409, "Ya existe esa vacuna con ese número de dosis")
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{vaccine_id}", status_code=204, dependencies=[can_edit])
def delete_vaccine(vaccine_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Vaccine, vaccine_id)
    if not obj:
        raise HTTPException(404, "Vacuna no encontrada")
    used = db.scalar(select(models.Vaccination.id).where(models.Vaccination.vaccine_id == vaccine_id).limit(1))
    if used:
        raise HTTPException(409, "No se puede eliminar: ya hay niños con esta vacuna registrada")
    db.delete(obj)
    db.commit()
