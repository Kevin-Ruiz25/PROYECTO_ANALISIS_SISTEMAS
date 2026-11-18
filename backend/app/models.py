import enum
from datetime import date, datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, Enum, Float, ForeignKey,
                        Integer, String, Table, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Role(str, enum.Enum):
    admin = "admin"
    health_staff = "health_staff"      # enfermera / doctor
    manager = "manager"                # encargado del centro de salud
    parent = "parent"


class Sex(str, enum.Enum):
    M = "M"
    F = "F"


class Channel(str, enum.Enum):
    email = "email"
    telegram = "telegram"
    whatsapp = "whatsapp"


class AlertType(str, enum.Enum):
    preventive = "preventiva"
    critical = "critica"


class VaccinationStatus(str, enum.Enum):
    complete = "completa"
    pending = "pendiente"


# Un niño puede tener varios padres/tutores y un padre varios niños
child_parents = Table(
    "child_parents", Base.metadata,
    Column("child_id", ForeignKey("children.id"), primary_key=True),
    Column("parent_id", ForeignKey("parents.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role), default=Role.health_staff)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Community(Base):
    __tablename__ = "communities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    location: Mapped[str | None] = mapped_column(String(300))
    estimated_families: Mapped[int] = mapped_column(Integer, default=0)

    parents = relationship("Parent", back_populates="community")
    children = relationship("Child", back_populates="community")


class Parent(Base):
    __tablename__ = "parents"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    dpi: Mapped[str] = mapped_column(String(30), unique=True)  # TODO paso de seguridad: cifrar
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    preferred_channel: Mapped[Channel] = mapped_column(Enum(Channel), default=Channel.email)
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # acceso del padre al carnet

    community = relationship("Community", back_populates="parents")
    children = relationship("Child", secondary=child_parents, back_populates="parents")


class Child(Base):
    __tablename__ = "children"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[date] = mapped_column(Date)
    sex: Mapped[Sex] = mapped_column(Enum(Sex))
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    qr_token: Mapped[str | None] = mapped_column(String(64), unique=True)  # paso del carnet QR
    qr_pin_hash: Mapped[str | None] = mapped_column(String(255))

    community = relationship("Community", back_populates="children")
    parents = relationship("Parent", secondary=child_parents, back_populates="children")
    growth_records = relationship("GrowthRecord", back_populates="child", cascade="all, delete-orphan")
    vaccinations = relationship("Vaccination", back_populates="child", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="child", cascade="all, delete-orphan")


class GrowthRecord(Base):
    __tablename__ = "growth_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    measured_on: Mapped[date] = mapped_column(Date)
    weight_kg: Mapped[float] = mapped_column(Float)
    height_cm: Mapped[float] = mapped_column(Float)
    age_months: Mapped[float] = mapped_column(Float)
    weight_percentile: Mapped[float | None] = mapped_column(Float)
    height_percentile: Mapped[float | None] = mapped_column(Float)

    child = relationship("Child", back_populates="growth_records")


class Vaccine(Base):
    __tablename__ = "vaccines"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    recommended_age_months: Mapped[int] = mapped_column(Integer)
    dose_number: Mapped[int] = mapped_column(Integer, default=1)


class Vaccination(Base):
    __tablename__ = "vaccinations"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    vaccine_id: Mapped[int] = mapped_column(ForeignKey("vaccines.id"))
    applied_on: Mapped[date | None] = mapped_column(Date)
    next_dose_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[VaccinationStatus] = mapped_column(Enum(VaccinationStatus), default=VaccinationStatus.pending)

    child = relationship("Child", back_populates="vaccinations")
    vaccine = relationship("Vaccine")


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    child_id: Mapped[int] = mapped_column(ForeignKey("children.id"))
    type: Mapped[AlertType] = mapped_column(Enum(AlertType))
    reason: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    child = relationship("Child", back_populates="alerts")


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int] = mapped_column(ForeignKey("parents.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    channel: Mapped[Channel] = mapped_column(Enum(Channel))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="pendiente")
