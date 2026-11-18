from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api/parents", tags=["Padres de familia"],
                   dependencies=[Depends(require_roles(*STAFF))])


@router.get("", response_model=list[schemas.ParentOut])
def list_parents(q: str | None = None, community_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(models.Parent).order_by(models.Parent.full_name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(models.Parent.full_name.ilike(like), models.Parent.dpi.ilike(like)))
    if community_id:
        stmt = stmt.where(models.Parent.community_id == community_id)
    return db.scalars(stmt).all()


@router.post("", response_model=schemas.ParentOut, status_code=201)
def create_parent(data: schemas.ParentCreate, db: Session = Depends(get_db)):
    if db.scalar(select(models.Parent).where(models.Parent.dpi == data.dpi)):
        raise HTTPException(409, "Ya existe un padre/tutor con ese DPI")
    obj = models.Parent(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{parent_id}", response_model=schemas.ParentOut)
def get_parent(parent_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Parent, parent_id)
    if not obj:
        raise HTTPException(404, "Padre/tutor no encontrado")
    return obj


@router.patch("/{parent_id}", response_model=schemas.ParentOut)
def update_parent(parent_id: int, data: schemas.ParentUpdate, db: Session = Depends(get_db)):
    obj = db.get(models.Parent, parent_id)
    if not obj:
        raise HTTPException(404, "Padre/tutor no encontrado")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{parent_id}", status_code=204)
def delete_parent(parent_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Parent, parent_id)
    if not obj:
        raise HTTPException(404, "Padre/tutor no encontrado")
    if obj.children:
        raise HTTPException(409, "No se puede eliminar: tiene niños asociados")
    db.execute(delete(models.Notification).where(models.Notification.parent_id == parent_id))
    user_id = obj.user_id
    db.delete(obj)
    if user_id:
        db.flush()
        account = db.get(models.User, user_id)
        if account and account.role == models.Role.parent:
            db.delete(account)
    db.commit()
