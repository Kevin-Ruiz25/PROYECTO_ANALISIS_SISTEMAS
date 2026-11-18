from datetime import date

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import Channel, Role, Sex


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Auth / usuarios
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: Role = Role.health_staff


class UserOut(ORM):
    id: int
    email: EmailStr
    full_name: str
    role: Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---- Comunidades
class CommunityBase(BaseModel):
    name: str = Field(min_length=2)
    location: str | None = None
    estimated_families: int = Field(0, ge=0)


class CommunityCreate(CommunityBase):
    pass


class CommunityOut(ORM, CommunityBase):
    id: int


# ---- Padres
class ParentBase(BaseModel):
    full_name: str = Field(min_length=2)
    dpi: str = Field(min_length=5)
    phone: str | None = None
    email: EmailStr | None = None
    preferred_channel: Channel = Channel.email
    community_id: int | None = None


class ParentCreate(ParentBase):
    pass


class ParentUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    preferred_channel: Channel | None = None
    community_id: int | None = None


class ParentOut(ORM, ParentBase):
    id: int
    user_id: int | None = None  # tiene cuenta para entrar al sistema


# ---- Niños
class ChildBase(BaseModel):
    full_name: str = Field(min_length=2)
    birth_date: date
    sex: Sex
    community_id: int | None = None


class ChildCreate(ChildBase):
    parent_ids: list[int] = []


class ChildUpdate(BaseModel):
    full_name: str | None = None
    birth_date: date | None = None
    sex: Sex | None = None
    community_id: int | None = None
    parent_ids: list[int] | None = None


class ChildOut(ORM, ChildBase):
    id: int
    parents: list[ParentOut] = []


# ---- Crecimiento
class GrowthCreate(BaseModel):
    measured_on: date
    weight_kg: float = Field(gt=0.3, lt=60, description="Peso en kilogramos")
    height_cm: float = Field(gt=20, lt=150, description="Longitud o talla en centímetros")


class GrowthOut(ORM):
    id: int
    child_id: int
    measured_on: date
    weight_kg: float
    height_cm: float
    age_months: float
    weight_percentile: float | None
    height_percentile: float | None


# ---- Vacunación
from .models import VaccinationStatus  # noqa: E402


class VaccineBase(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    recommended_age_months: int = Field(ge=0, le=216, description="0 = al nacer")
    dose_number: int = Field(1, ge=1, le=20)


class VaccineCreate(VaccineBase):
    pass


class VaccineOut(ORM, VaccineBase):
    id: int


class VaccinationCreate(BaseModel):
    vaccine_id: int
    applied_on: date
    next_dose_on: date | None = None


class VaccinationOut(ORM):
    id: int
    child_id: int
    vaccine_id: int
    applied_on: date | None
    next_dose_on: date | None
    status: VaccinationStatus


class CardItem(BaseModel):
    vaccine: VaccineOut
    due_date: date
    status: str  # completa | atrasada | pendiente | proxima
    vaccination_id: int | None
    applied_on: date | None
    next_dose_on: date | None


class CardSummary(BaseModel):
    total: int
    completa: int
    atrasada: int
    pendiente: int
    proxima: int


class CardOut(BaseModel):
    child_id: int
    summary: CardSummary
    items: list[CardItem]


# ---- Alertas y notificaciones
from datetime import datetime  # noqa: E402


class AlertOut(BaseModel):
    id: int
    child_id: int
    child_name: str
    community_name: str | None
    type: str          # preventiva | critica
    reason: str        # peso_bajo | peso_alto | sin_controles | vacunas_atrasadas
    message: str
    created_at: datetime
    resolved: bool


class NotificationOut(BaseModel):
    id: int
    parent_id: int
    parent_name: str
    child_id: int | None
    child_name: str | None
    alert_id: int | None
    channel: str
    subject: str
    status: str  # pendiente | enviada | simulada | error | sin_contacto | canal_no_disponible
    sent_at: datetime | None


# ---- Carnet digital
class CarnetStatus(BaseModel):
    has_carnet: bool
    url: str | None = None
    qr: str | None = None   # data URI (SVG) del código QR


class CarnetIssued(BaseModel):
    url: str
    qr: str
    pin: str                # se muestra una sola vez


class PinIssued(BaseModel):
    pin: str


class PinIn(BaseModel):
    pin: str = Field(min_length=1, max_length=20)


class MyChild(BaseModel):
    child_id: int
    full_name: str
    birth_date: date
    has_carnet: bool
    token: str | None = None


class CarnetOut(BaseModel):
    child_name: str
    birth_date: date
    sex: str
    community_name: str | None
    vaccination: CardOut
    growth: list[GrowthOut]   # últimos registros, del más reciente al más antiguo


class AccessGranted(BaseModel):
    email: str
    temporary_password: str
    created: bool


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=100)
