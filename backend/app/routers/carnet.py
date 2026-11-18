from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import carnet, models, schemas, vaccination
from ..database import get_db
from ..deps import STAFF, require_roles
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api", tags=["Carnet digital"])
staff = Depends(require_roles(*STAFF))
parent_only = require_roles(models.Role.parent)


def _child(db: Session, child_id: int) -> models.Child:
    child = db.get(models.Child, child_id)
    if not child:
        raise HTTPException(404, "Niño no encontrado")
    return child


# ---------------------------------------------------------------- Personal de salud
@router.get("/children/{child_id}/carnet", response_model=schemas.CarnetStatus, dependencies=[staff])
def carnet_status(child_id: int, db: Session = Depends(get_db)):
    child = _child(db, child_id)
    if not child.qr_token:
        return {"has_carnet": False}
    url = carnet.carnet_url(child.qr_token)
    return {"has_carnet": True, "url": url, "qr": carnet.qr_data_uri(url)}


@router.post("/children/{child_id}/carnet", response_model=schemas.CarnetIssued, status_code=201,
             dependencies=[staff])
def issue_carnet(child_id: int, db: Session = Depends(get_db)):
    """Genera el carnet. Si ya existía, emite un QR y un PIN nuevos (el QR anterior deja de servir)."""
    child = _child(db, child_id)
    pin = carnet.new_pin()
    child.qr_token = carnet.new_token()
    child.qr_pin_hash = hash_password(pin)
    db.commit()
    carnet.reset_child(child.id)
    url = carnet.carnet_url(child.qr_token)
    return {"url": url, "qr": carnet.qr_data_uri(url), "pin": pin}


@router.post("/children/{child_id}/carnet/pin", response_model=schemas.PinIssued, dependencies=[staff])
def new_pin(child_id: int, db: Session = Depends(get_db)):
    """PIN nuevo con el mismo QR (PIN olvidado o cuenta bloqueada)."""
    child = _child(db, child_id)
    if not child.qr_token:
        raise HTTPException(409, "Este niño aún no tiene carnet. Genéralo primero.")
    pin = carnet.new_pin()
    child.qr_pin_hash = hash_password(pin)
    db.commit()
    carnet.reset_child(child.id)
    return {"pin": pin}


@router.delete("/children/{child_id}/carnet", status_code=204, dependencies=[staff])
def revoke_carnet(child_id: int, db: Session = Depends(get_db)):
    child = _child(db, child_id)
    child.qr_token = None
    child.qr_pin_hash = None
    db.commit()
    carnet.reset_child(child.id)


@router.post("/parents/{parent_id}/access", response_model=schemas.AccessGranted, dependencies=[staff])
def grant_access(parent_id: int, db: Session = Depends(get_db)):
    """Crea (o restablece) la cuenta del padre/tutor con una contraseña temporal que se muestra una vez."""
    parent = db.get(models.Parent, parent_id)
    if not parent:
        raise HTTPException(404, "Padre/tutor no encontrado")
    if not parent.email:
        raise HTTPException(422, "Registra primero el correo electrónico del padre o tutor.")
    temp = carnet.temp_password()
    created = parent.user_id is None
    if created:
        if db.scalar(select(models.User).where(models.User.email == parent.email)):
            raise HTTPException(409, "Ya existe un usuario con ese correo electrónico.")
        user = models.User(email=parent.email, full_name=parent.full_name, role=models.Role.parent,
                           hashed_password=hash_password(temp))
        db.add(user)
        db.flush()
        parent.user_id = user.id
    else:
        user = db.get(models.User, parent.user_id)
        if user.email != parent.email:  # el correo se corrigió después de crear la cuenta
            if db.scalar(select(models.User).where(models.User.email == parent.email)):
                raise HTTPException(409, "Ya existe un usuario con ese correo electrónico.")
            user.email = parent.email
        user.hashed_password = hash_password(temp)
        user.is_active = True
    db.commit()
    return {"email": user.email, "temporary_password": temp, "created": created}


# ---------------------------------------------------------------- Padres de familia
def _my_children(db: Session, user: models.User) -> list[models.Child]:
    parents = db.scalars(select(models.Parent).where(models.Parent.user_id == user.id)).all()
    seen: dict[int, models.Child] = {}
    for p in parents:
        for c in p.children:
            seen[c.id] = c
    return sorted(seen.values(), key=lambda c: c.full_name)


@router.get("/me/children", response_model=list[schemas.MyChild])
def my_children(user: models.User = Depends(parent_only), db: Session = Depends(get_db)):
    return [{"child_id": c.id, "full_name": c.full_name, "birth_date": c.birth_date,
             "has_carnet": bool(c.qr_token), "token": c.qr_token} for c in _my_children(db, user)]


@router.post("/carnet/{token}/open", response_model=schemas.CarnetOut)
def open_carnet(token: str, data: schemas.PinIn, user: models.User = Depends(parent_only),
                db: Session = Depends(get_db)):
    child = db.scalar(select(models.Child).where(models.Child.qr_token == token))
    # Mismo error si el código no existe o si el niño no es de este padre: no se revela cuál de los dos.
    if not child or not any(p.user_id == user.id for p in child.parents):
        raise HTTPException(404, "Carnet no encontrado o sin acceso.")

    wait = carnet.locked_minutes(user.id, child.id)
    if wait:
        raise HTTPException(429, f"Demasiados intentos fallidos. Intenta de nuevo en {wait} minutos "
                                 "o pide un PIN nuevo en el centro de salud.")
    if not child.qr_pin_hash or not verify_password(data.pin.strip(), child.qr_pin_hash):
        left = carnet.register_failure(user.id, child.id)
        if left == 0:
            raise HTTPException(429, f"PIN incorrecto. Se bloqueó el acceso por {carnet.LOCK_SECONDS // 60} minutos.")
        raise HTTPException(403, f"PIN incorrecto. Te quedan {left} intentos.")
    carnet.register_success(user.id, child.id)

    catalog = db.scalars(select(models.Vaccine)).all()
    records = sorted(child.growth_records, key=lambda r: r.measured_on, reverse=True)[:5]
    return {
        "child_name": child.full_name, "birth_date": child.birth_date, "sex": child.sex.value,
        "community_name": child.community.name if child.community else None,
        "vaccination": vaccination.build_card(child, catalog), "growth": records,
    }
