import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from . import alerts as alert_engine
from . import config, models
from .database import Base, SessionLocal, engine
from .routers import alerts, auth, carnet, children, communities, growth, parents, reports, vaccinations, vaccines
from .security import hash_password
from .vaccines_seed import SEED_VACCINES

app = FastAPI(title="SCCVI - Control de Crecimiento y Vacunación Infantil", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # frontend Vite
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, communities, parents, children, growth, vaccines, vaccinations, alerts, carnet, reports):
    app.include_router(r.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)  # más adelante: migraciones con Alembic
    with SessionLocal() as db:
        if not db.scalar(select(models.User).limit(1)):
            db.add(models.User(email="admin@sccvi.org", full_name="Administrador",
                               hashed_password=hash_password("Admin1234!"), role=models.Role.admin))
            db.commit()
        if not db.scalar(select(models.Vaccine).limit(1)):
            db.add_all(models.Vaccine(name=n, dose_number=d, recommended_age_months=a) for n, d, a in SEED_VACCINES)
            db.commit()
    if config.ALERT_CHECK_HOURS > 0:
        asyncio.create_task(_periodic_alert_check())


async def _periodic_alert_check():
    """Revisa todos los niños cada ALERT_CHECK_HOURS (la primera vez tras ese tiempo)."""
    while True:
        await asyncio.sleep(config.ALERT_CHECK_HOURS * 3600)
        try:
            await asyncio.to_thread(alert_engine.run_scheduled_check)
        except Exception:  # noqa: BLE001 - la revisión nunca debe tumbar el servidor
            pass


@app.get("/api/health", tags=["Sistema"])
def health():
    return {"status": "ok"}
