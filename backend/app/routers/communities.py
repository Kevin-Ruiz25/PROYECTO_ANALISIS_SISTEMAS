from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import STAFF, require_roles

router = APIRouter(prefix="/api/communities", tags=["Comunidades"],
                   dependencies=[Depends(require_roles(*STAFF))])


@router.get("", response_model=list[schemas.CommunityOut])
def list_communities(db: Session = Depends(get_db)):
    return db.scalars(select(models.Community).order_by(models.Community.name)).all()


@router.post("", response_model=schemas.CommunityOut, status_code=201)
def create_community(data: schemas.CommunityCreate, db: Session = Depends(get_db)):
    if db.scalar(select(models.Community).where(models.Community.name == data.name)):
        raise HTTPException(409, "Ya existe una comunidad con ese nombre")
    obj = models.Community(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{community_id}", response_model=schemas.CommunityOut)
def get_community(community_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Community, community_id)
    if not obj:
        raise HTTPException(404, "Comunidad no encontrada")
    return obj


@router.put("/{community_id}", response_model=schemas.CommunityOut)
def update_community(community_id: int, data: schemas.CommunityCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Community, community_id)
    if not obj:
        raise HTTPException(404, "Comunidad no encontrada")
    for k, v in data.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{community_id}", status_code=204)
def delete_community(community_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Community, community_id)
    if not obj:
        raise HTTPException(404, "Comunidad no encontrada")
    if obj.parents or obj.children:
        raise HTTPException(409, "No se puede eliminar: tiene padres o niños asociados")
    db.delete(obj)
    db.commit()
