
import hashlib
import hmac
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, JSON, String,
    create_engine, desc, select
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ["JWT_SECRET"]
ADMIN_USERNAME = os.environ["ADMIN_USERNAME"]
ADMIN_PASSWORD = os.environ["ADMIN_PASSWORD"]
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    connect_args={"sslmode": "require"},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


def utc(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class Base(DeclarativeBase):
    pass


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255))
    os_version: Mapped[str] = mapped_column(String(255))
    cpu_model: Mapped[str] = mapped_column(String(255))
    cpu_count: Mapped[int] = mapped_column(Integer)
    total_ram_mb: Mapped[float] = mapped_column(Float)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnrollmentCode(Base):
    __tablename__ = "enrollment_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    cpu_percent: Mapped[float] = mapped_column(Float)
    ram_percent: Mapped[float] = mapped_column(Float)
    ram_used_mb: Mapped[float] = mapped_column(Float)
    ram_total_mb: Mapped[float] = mapped_column(Float)
    disk_percent: Mapped[float] = mapped_column(Float)
    disk_used_gb: Mapped[float] = mapped_column(Float)
    disk_total_gb: Mapped[float] = mapped_column(Float)
    battery_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    battery_plugged: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cpu_temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[float] = mapped_column(Float)
    network_sent_bytes: Mapped[int] = mapped_column(Integer)
    network_recv_bytes: Mapped[int] = mapped_column(Integer)
    top_processes: Mapped[list] = mapped_column(JSON, default=list)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    message: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoginBody(BaseModel):
    username: str
    password: str


class EnrollBody(BaseModel):
    code: str = Field(min_length=16, max_length=200)
    hostname: str = Field(min_length=1, max_length=255)
    os_version: str = Field(max_length=255)
    cpu_model: str = Field(max_length=255)
    cpu_count: int = Field(ge=1, le=1024)
    total_ram_mb: float = Field(gt=0)


class ReportBody(BaseModel):
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)
    ram_used_mb: float = Field(ge=0)
    ram_total_mb: float = Field(gt=0)
    disk_percent: float = Field(ge=0, le=100)
    disk_used_gb: float = Field(ge=0)
    disk_total_gb: float = Field(gt=0)
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    battery_plugged: bool | None = None
    cpu_temp_c: float | None = Field(default=None, ge=-30, le=150)
    uptime_seconds: float = Field(ge=0)
    network_sent_bytes: int = Field(ge=0)
    network_recv_bytes: int = Field(ge=0)
    top_processes: list[dict[str, Any]] = Field(default_factory=list, max_length=20)


bearer = HTTPBearer(auto_error=False)


def get_admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        if claims.get("role") != "admin" or claims.get("sub") != ADMIN_USERNAME:
            raise HTTPException(status_code=403, detail="Administrator required")
        return claims
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_device_id(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(status_code=401, detail="Device token required")
    token_hash = digest(credentials.credentials)
    with SessionLocal() as db:
        device = db.scalar(
            select(Device).where(
                Device.token_hash == token_hash,
                Device.is_active.is_(True),
            )
        )
        if device is None:
            raise HTTPException(status_code=401, detail="Invalid device token")
        return device.id


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="Helpdesk Monitoring API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/login")
def login(body: LoginBody):
    if not (
        hmac.compare_digest(body.username, ADMIN_USERNAME)
        and hmac.compare_digest(body.password, ADMIN_PASSWORD)
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = jwt.encode(
        {
            "sub": ADMIN_USERNAME,
            "role": "admin",
            "exp": now() + timedelta(minutes=JWT_EXPIRE_MINUTES),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"access_token": token, "token_type": "bearer"}


@app.post("/admin/enrollment-codes")
def create_code(_=Depends(get_admin)):
    code = secrets.token_urlsafe(32)
    with SessionLocal.begin() as db:
        db.add(
            EnrollmentCode(
                code_hash=digest(code),
                expires_at=now() + timedelta(minutes=15),
            )
        )
    return {"code": code, "expires_in_minutes": 15}


@app.post("/agent/enroll")
def enroll(body: EnrollBody):
    with SessionLocal.begin() as db:
        entry = db.scalar(
            select(EnrollmentCode)
            .where(EnrollmentCode.code_hash == digest(body.code))
            .with_for_update()
        )
        if (
            entry is None
            or entry.used_at is not None
            or utc(entry.expires_at) <= now()
        ):
            raise HTTPException(status_code=401, detail="Invalid, expired, or used code")

        device_id = secrets.token_hex(16)
        device_token = secrets.token_urlsafe(48)

        db.add(Device(
            id=device_id,
            hostname=body.hostname,
            os_version=body.os_version,
            cpu_model=body.cpu_model,
            cpu_count=body.cpu_count,
            total_ram_mb=body.total_ram_mb,
            token_hash=digest(device_token),
            last_seen=now(),
        ))
        entry.used_at = now()

    # Return the secret only once; store only its hash in the database.
    return {"device_id": device_id, "device_token": device_token}


@app.post("/agent/report")
def report(body: ReportBody, device_id: str = Depends(get_device_id)):
    with SessionLocal.begin() as db:
        device = db.get(Device, device_id)
        if device is None or not device.is_active:
            raise HTTPException(status_code=401, detail="Device disabled")

        device.last_seen = now()
        db.add(Metric(device_id=device_id, **body.model_dump()))

        checks = [
            ("cpu", body.cpu_percent >= 90, f"CPU usage: {body.cpu_percent:.1f}%"),
            ("ram", body.ram_percent >= 90, f"RAM usage: {body.ram_percent:.1f}%"),
            ("disk", body.disk_percent >= 90, f"Disk usage: {body.disk_percent:.1f}%"),
        ]

        for kind, breached, message in checks:
            alert = db.scalar(select(Alert).where(
                Alert.device_id == device_id,
                Alert.kind == kind,
                Alert.active.is_(True),
            ))
            if breached and alert is None:
                db.add(Alert(device_id=device_id, kind=kind, message=message))
            elif breached:
                alert.message = message
            elif alert is not None:
                alert.active = False
                alert.resolved_at = now()

    return {"accepted": True}


@app.get("/devices")
def devices(_=Depends(get_admin)):
    with SessionLocal() as db:
        all_devices = db.scalars(select(Device).order_by(Device.hostname)).all()
        result = []

        for d in all_devices:
            metric = db.scalar(
                select(Metric)
                .where(Metric.device_id == d.id)
                .order_by(desc(Metric.timestamp))
                .limit(1)
            )
            last_seen = utc(d.last_seen)
            online = bool(
                d.is_active and last_seen
                and (now() - last_seen).total_seconds() < 90
            )

            latest = None
            if metric:
                latest = {
                    "timestamp": utc(metric.timestamp).isoformat(),
                    "cpu_percent": metric.cpu_percent,
                    "ram_percent": metric.ram_percent,
                    "disk_percent": metric.disk_percent,
                    "battery_percent": metric.battery_percent,
                    "battery_plugged": metric.battery_plugged,
                    "cpu_temp_c": metric.cpu_temp_c,
                    "uptime_seconds": metric.uptime_seconds,
                    "top_processes": metric.top_processes,
                }

            result.append({
                "id": d.id,
                "hostname": d.hostname,
                "os_version": d.os_version,
                "cpu_model": d.cpu_model,
                "cpu_count": d.cpu_count,
                "total_ram_mb": d.total_ram_mb,
                "last_seen": last_seen.isoformat() if last_seen else None,
                "online": online,
                "is_active": d.is_active,
                "latest": latest,
            })
        return result


@app.get("/devices/{device_id}/metrics")
def metrics(device_id: str, limit: int = 60, _=Depends(get_admin)):
    limit = max(1, min(limit, 500))
    with SessionLocal() as db:
        if db.get(Device, device_id) is None:
            raise HTTPException(status_code=404, detail="Device not found")

        rows = db.scalars(
            select(Metric)
            .where(Metric.device_id == device_id)
            .order_by(desc(Metric.timestamp))
            .limit(limit)
        ).all()

        return [{
            "timestamp": utc(m.timestamp).isoformat(),
            "cpu_percent": m.cpu_percent,
            "ram_percent": m.ram_percent,
            "disk_percent": m.disk_percent,
            "cpu_temp_c": m.cpu_temp_c,
            "battery_percent": m.battery_percent,
            "top_processes": m.top_processes,
        } for m in reversed(rows)]


@app.get("/alerts")
def alerts(_=Depends(get_admin)):
    with SessionLocal() as db:
        rows = db.execute(
            select(Alert, Device.hostname)
            .join(Device, Alert.device_id == Device.id)
            .where(Alert.active.is_(True))
            .order_by(desc(Alert.created_at))
            .limit(100)
        ).all()

        return [{
            "id": a.id,
            "hostname": hostname,
            "kind": a.kind,
            "message": a.message,
            "created_at": utc(a.created_at).isoformat(),
        } for a, hostname in rows]


@app.post("/admin/devices/{device_id}/disable")
def disable_device(device_id: str, _=Depends(get_admin)):
    with SessionLocal.begin() as db:
        device = db.get(Device, device_id)
        if device is None:
            raise HTTPException(status_code=404, detail="Device not found")
        device.is_active = False
    return {"disabled": True}
