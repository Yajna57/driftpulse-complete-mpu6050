from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import Base, engine
from .routers import health, readings

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Phase-1 convenience. Use Alembic migrations in a production version.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.1.0-mpu6050",
    description=(
        "Educational personalized physiological-drift monitoring API using "
        "AD8232, MAX30102, LM35 and MPU6050. Not a medical diagnostic system."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(readings.router)
app.include_router(health.router)


@app.get("/")
def root() -> dict:
    return {
        "name": "DriftPulse API",
        "phase": 1,
        "hardware": ["MAX30102", "AD8232", "LM35", "MPU6050"],
        "docs": "/docs",
    }


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok", "service": "driftpulse-api"}
