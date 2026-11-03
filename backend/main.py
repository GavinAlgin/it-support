import os
import sqlite3
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from jose import jwt, JWTError
from passlib.context import CryptContext

APP_NAME = "CloudMonitor API"
DB_PATH = os.getenv("CLOUDMONITOR_DB", "cloudmonitor.db")
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE-THIS-TO-A-LONG-RANDOM-SECRET")
JWT_ALGORITHM = "HS256"
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "12"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe-Immediately-123!")
ENROLLMENT_CODE = os.getenv("ENROLLMENT_CODE", "TECHLOOM-ENROL-2026")
HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI(title=APP_NAME, version="1.0.0")

origins = [x.strip() for x in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'admin',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS enrollment_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_hash TEXT UNIQUE NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            used_at TEXT
        );
        CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            assigned_user TEXT DEFAULT 'Unassigned',
            user_email TEXT DEFAULT '',
            organisation TEXT DEFAULT '',
            serial TEXT DEFAULT '',
            hostname TEXT NOT NULL,
            os_name TEXT DEFAULT '',
            agent_version TEXT DEFAULT '',
            device_token_hash TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'Offline',
            created_at TEXT NOT NULL,
            last_seen TEXT,
            latest_metrics TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            received_at TEXT NOT NULL,
            metrics TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_heartbeats_device_time
            ON heartbeats(device_id, received_at);
        CREATE TABLE IF NOT EXISTS permission_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
            scope TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            responded_at TEXT
        );
        """)
        user = db.execute("SELECT id FROM users WHERE username=?", (ADMIN_USERNAME,)).fetchone()
        if not user:
            db.execute(
                "INSERT INTO users(username,password_hash,role,created_at) VALUES(?,?,?,?)",
                (ADMIN_USERNAME, pwd_context.hash(ADMIN_PASSWORD), "admin", now_iso())
            )
        code_hash = hashlib.sha256(ENROLLMENT_CODE.encode()).hexdigest()
        exists = db.execute("SELECT id FROM enrollment_codes WHERE code_hash=?", (code_hash,)).fetchone()
        if not exists:
            db.execute(
                "INSERT INTO enrollment_codes(code_hash,active,created_at) VALUES(?,1,?)",
                (code_hash, now_iso())
            )

@app.on_event("startup")
def startup():
    init_db()

def make_token(subject: str, kind: str):
    expiry = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": subject, "kind": kind, "exp": expiry}, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str, expected_kind: str):
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("kind") != expected_kind or not payload.get("sub"):
            raise ValueError()
        return payload["sub"]
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def bearer_value(authorization: Optional[str]):
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    return authorization.split(" ", 1)[1].strip()

def current_admin(authorization: Optional[str] = Header(None)):
    username = decode_token(bearer_value(authorization), "user")
    with connect() as db:
        row = db.execute("SELECT id,username,role FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return dict(row)

def current_device(authorization: Optional[str] = Header(None)):
    device_id = decode_token(bearer_value(authorization), "device")
    with connect() as db:
        row = db.execute("SELECT id,device_token_hash FROM devices WHERE id=?", (device_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Device not enrolled")
    return dict(row)

class LoginBody(BaseModel):
    username: str
    password: str

class EnrollBody(BaseModel):
    code: str
    hostname: str
    os_name: str = ""
    agent_version: str = "1.0.0"

class HeartbeatBody(BaseModel):
    cpu_percent: Optional[float] = None
    cpu_model: str = ""
    ram_percent: Optional[float] = None
    ram_used_mb: Optional[float] = None
    ram_total_gb: Optional[float] = None
    disk_percent: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    disk_name: str = ""
    battery_percent: Optional[float] = None
    battery_plugged_in: Optional[bool] = None
    uptime_seconds: Optional[int] = None
    ip_address: str = ""
    serial: str = ""
    processes: list[dict] = Field(default_factory=list)

class DeviceUpdate(BaseModel):
    assigned_user: Optional[str] = None
    user_email: Optional[str] = None
    organisation: Optional[str] = None
    serial: Optional[str] = None
    name: Optional[str] = None

class EnrollmentCodeBody(BaseModel):
    code: Optional[str] = None

class PermissionRequestBody(BaseModel):
    device_id: str
    scope: str
    description: str = ""

class PermissionResponseBody(BaseModel):
    request_id: int
    decision: str

DEFAULT_POLICY = {
    "monitoring_enabled": True,
    "permissions": {
        "system_metrics": True,
        "disk_metrics": True,
        "battery_metrics": True,
        "uptime_metrics": True,
        "process_metadata": True
    }
}

@app.get("/health")
def health():
    return {"status": "ok", "service": APP_NAME, "time": now_iso()}

@app.post("/api/v1/auth/login")
def login(body: LoginBody):
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    if not user or not pwd_context.verify(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    return {"access_token": make_token(body.username, "user"), "token_type": "bearer"}

@app.post("/api/v1/agent/enroll")
def enroll(body: EnrollBody, admin=Depends(current_admin)):
    supplied_hash = hashlib.sha256(body.code.strip().encode()).hexdigest()
    with connect() as db:
        code = db.execute(
            "SELECT * FROM enrollment_codes WHERE code_hash=? AND active=1",
            (supplied_hash,)
        ).fetchone()
        if not code:
            raise HTTPException(status_code=400, detail="Invalid or inactive enrollment code")
        device_id = "dev_" + secrets.token_hex(8)
        raw_token = secrets.token_urlsafe(40)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        db.execute("UPDATE enrollment_codes SET active=0,used_at=? WHERE id=?", (now_iso(), code["id"]))
        db.execute("""
            INSERT INTO devices(id,name,hostname,os_name,agent_version,device_token_hash,created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (device_id, body.hostname, body.hostname, body.os_name, body.agent_version, token_hash, now_iso()))
    return {"device_id": device_id, "device_token": raw_token}

@app.get("/api/v1/agent/policy")
def agent_policy(device=Depends(current_device)):
    return DEFAULT_POLICY

@app.post("/api/v1/agent/heartbeat")
def heartbeat(body: HeartbeatBody, device=Depends(current_device)):
    payload = body.model_dump()
    with connect() as db:
        db.execute("""
            UPDATE devices SET state='Online',last_seen=?,latest_metrics=? WHERE id=?
        """, (now_iso(), __import__("json").dumps(payload), device["id"]))
        db.execute(
            "INSERT INTO heartbeats(device_id,received_at,metrics) VALUES(?,?,?)",
            (device["id"], now_iso(), __import__("json").dumps(payload))
        )
        db.execute("""
            DELETE FROM heartbeats WHERE device_id=? AND id NOT IN
            (SELECT id FROM heartbeats WHERE device_id=? ORDER BY id DESC LIMIT 300)
        """, (device["id"], device["id"]))
    return {"ok": True, "received_at": now_iso()}

@app.get("/api/v1/agent/permission-requests")
def agent_permission_requests(device=Depends(current_device)):
    with connect() as db:
        rows = db.execute(
            "SELECT id,scope,description FROM permission_requests WHERE device_id=? AND status='pending' ORDER BY id",
            (device["id"],)
        ).fetchall()
    return {"requests": [dict(x) for x in rows]}

@app.post("/api/v1/agent/permission-responses")
def agent_permission_response(body: PermissionResponseBody, device=Depends(current_device)):
    if body.decision not in ("approved", "denied"):
        raise HTTPException(status_code=400, detail="Decision must be approved or denied")
    with connect() as db:
        cur = db.execute("""
            UPDATE permission_requests SET status=?,responded_at=?
            WHERE id=? AND device_id=? AND status='pending'
        """, (body.decision, now_iso(), body.request_id, device["id"]))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pending request not found")
    return {"ok": True}

@app.get("/api/v1/dashboard/devices")
def dashboard_devices(admin=Depends(current_admin)):
    import json
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    with connect() as db:
        rows = db.execute("SELECT * FROM devices ORDER BY created_at DESC").fetchall()
    result = []
    for row in rows:
        item = dict(row)
        last_seen = item.get("last_seen")
        online = False
        if last_seen:
            try:
                online = datetime.fromisoformat(last_seen) >= cutoff
            except ValueError:
                pass
        metrics = json.loads(item.get("latest_metrics") or "{}")
        item["state"] = "Online" if online else "Offline"
        item["metrics"] = metrics
        item.pop("device_token_hash", None)
        item.pop("latest_metrics", None)
        result.append(item)
    return {"devices": result}

@app.get("/api/v1/dashboard/devices/{device_id}")
def dashboard_device(device_id: str, admin=Depends(current_admin)):
    import json
    with connect() as db:
        row = db.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Device not found")
        processes = db.execute(
            "SELECT metrics FROM heartbeats WHERE device_id=? ORDER BY id DESC LIMIT 1",
            (device_id,)
        ).fetchone()
        history = db.execute(
            "SELECT received_at,metrics FROM heartbeats WHERE device_id=? ORDER BY id DESC LIMIT 100",
            (device_id,)
        ).fetchall()
    item = dict(row)
    item["metrics"] = json.loads(item.pop("latest_metrics") or "{}")
    item.pop("device_token_hash", None)
    item["processes"] = item["metrics"].get("processes", [])
    item["history"] = [
        {"received_at": h["received_at"], **json.loads(h["metrics"])}
        for h in reversed(history)
    ]
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    try:
        item["state"] = "Online" if item["last_seen"] and datetime.fromisoformat(item["last_seen"]) >= cutoff else "Offline"
    except (ValueError, TypeError):
        item["state"] = "Offline"
    return item

@app.patch("/api/v1/dashboard/devices/{device_id}")
def update_device(device_id: str, body: DeviceUpdate, admin=Depends(current_admin)):
    fields = body.model_dump(exclude_none=True)
    if not fields:
        return {"ok": True}
    allowed = {"assigned_user", "user_email", "organisation", "serial", "name"}
    if set(fields) - allowed:
        raise HTTPException(status_code=400, detail="Unsupported field")
    sql = "UPDATE devices SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?"
    with connect() as db:
        cur = db.execute(sql, (*fields.values(), device_id))
        if not cur.rowcount:
            raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True}

@app.post("/api/v1/dashboard/enrollment-codes")
def create_enrollment_code(body: EnrollmentCodeBody, admin=Depends(current_admin)):
    code = (body.code or secrets.token_urlsafe(12)).strip()
    if len(code) < 8:
        raise HTTPException(status_code=400, detail="Enrollment code must be at least 8 characters")
    digest = hashlib.sha256(code.encode()).hexdigest()
    with connect() as db:
        db.execute("INSERT INTO enrollment_codes(code_hash,active,created_at) VALUES(?,1,?)", (digest, now_iso()))
    return {"code": code, "active": True}

@app.get("/api/v1/dashboard/permission-requests")
def list_permission_requests(admin=Depends(current_admin)):
    with connect() as db:
        rows = db.execute("""
            SELECT p.*,d.name AS device_name FROM permission_requests p
            JOIN devices d ON d.id=p.device_id ORDER BY p.id DESC
        """).fetchall()
    return {"requests": [dict(x) for x in rows]}

@app.post("/api/v1/dashboard/permission-requests")
def create_permission_request(body: PermissionRequestBody, admin=Depends(current_admin)):
    with connect() as db:
        exists = db.execute("SELECT id FROM devices WHERE id=?", (body.device_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="Device not found")
        cur = db.execute("""
            INSERT INTO permission_requests(device_id,scope,description,created_at)
            VALUES(?,?,?,?)
        """, (body.device_id, body.scope, body.description, now_iso()))
    return {"id": cur.lastrowid, "status": "pending"}

@app.get("/api/v1/dashboard/summary")
def dashboard_summary(admin=Depends(current_admin)):
    devices = dashboard_devices(admin)
    return {
        "total": len(devices["devices"]),
        "online": sum(d["state"] == "Online" for d in devices["devices"]),
        "offline": sum(d["state"] == "Offline" for d in devices["devices"]),
        "devices": devices["devices"]
    }

@app.get("/api/v1/dashboard/tickets")
def dashboard_tickets(admin=Depends(current_admin)):
    # Ticket management is not present in the supplied frontend or agent backend contract.
    return {"tickets": []}
