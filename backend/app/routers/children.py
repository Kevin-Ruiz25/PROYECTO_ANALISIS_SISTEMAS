from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .. import growth, models, schemas
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api/children", tags=["Niños"],
                   dependencies=[Depends(require_roles(*STAFF))])


def _load_parents(db: Session, ids: list[int]) -> list[models.Parent]:
    parents = list(db.scalars(select(models.Parent).where(models.Parent.id.in_(ids))).all()) if ids else []
    if len(parents) != len(set(ids)):
        raise HTTPException(422, "Alguno de los padres indicados no existe")
    return parents


@router.get("", response_model=list[schemas.ChildOut])
def list_children(q: str | None = None, community_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Child).order_by(models.Child.full_name)
    if q:
        stmt = stmt.where(models.Child.full_name.ilike(f"%{q}%"))
    if community_id:
        stmt = stmt.where(models.Child.community_id == community_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.ChildOut, status_code=201)
def create_child(data: schemas.ChildCreate, db: Session = Depends(get_db)):
    values = data.model_dump(exclude={"parent_ids"})
    obj = models.Child(**values, parents=_load_parents(db, data.parent_ids))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{child_id}", response_model=schemas.ChildOut)
def get_child(child_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Child, child_id)
    if not obj:
        raise HTTPException(404, "Niño no encontrado")
    return obj


@router.patch("/{child_id}", response_model=schemas.ChildOut)
def update_child(child_id: int, data: schemas.ChildUpdate, db: Session = Depends(get_db)):
    obj = db.get(models.Child, child_id)
    if not obj:
        raise HTTPException(404, "Niño no encontrado")
    changes = data.model_dump(exclude_unset=True)
    parent_ids = changes.pop("parent_ids", None)
    for k, v in changes.items():
        setattr(obj, k, v)
    if parent_ids is not None:
        obj.parents = _load_parents(db, parent_ids)
    if "birth_date" in changes or "sex" in changes:
        growth.recompute_records(obj)  # los percentiles dependen de la edad y el sexo
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{child_id}", status_code=204)
def delete_child(child_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Child, child_id)
    if not obj:
        raise HTTPException(404, "Niño no encontrado")
    alert_ids = [a.id for a in obj.alerts]
    if alert_ids:  # las notificaciones referencian las alertas del niño
        db.execute(delete(models.Notification).where(models.Notification.alert_id.in_(alert_ids)))
    db.delete(obj)
    db.commit()
