from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["Autenticación"])


@router.post("/login", response_model=schemas.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(models.User).where(models.User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")
    return schemas.Token(access_token=create_access_token(user.id, user.role.value), user=user)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(get_current_user)):
    return user


@router.post("/users", response_model=schemas.UserOut, status_code=201)
def create_user(data: schemas.UserCreate, db: Session = Depends(get_db),
                _: models.User = Depends(require_roles(models.Role.admin))):
    if db.scalar(select(models.User).where(models.User.email == data.email)):
        raise HTTPException(409, "Ya existe un usuario con ese correo")
    user = models.User(email=data.email, full_name=data.full_name, role=data.role,
                       hashed_password=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/change-password", status_code=204)
def change_password(data: schemas.PasswordChange, db: Session = Depends(get_db),
                    user: models.User = Depends(get_current_user)):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "La contraseña actual no es correcta")  # 400 y no 401: no debe cerrar la sesión
    if data.current_password == data.new_password:
        raise HTTPException(400, "La contraseña nueva debe ser distinta de la actual")
    user.hashed_password = hash_password(data.new_password)
    db.commit()
