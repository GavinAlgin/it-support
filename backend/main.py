
import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from supabase import create_client, Client


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

if not all([
    SUPABASE_URL,
    SUPABASE_KEY,
    SUPABASE_SERVICE_ROLE_KEY
]):
    raise RuntimeError("Missing Supabase environment variables")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

app = FastAPI(
    title="helpdesk API",
    version="1.0.0"
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def utc_now():
    return datetime.now(timezone.utc)


def get_profile(user_id: str):
    result = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=403,
            detail="User profile not found"
        )

    return result.data[0]


def get_user(
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token"
        )

    token = authorization.split(" ", 1)[1]

    try:
        result = supabase.auth.get_user(token)

        if not result.user:
            raise ValueError("Invalid user")

        return get_profile(str(result.user.id))

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired login token"
        )


def require_admin(user=Depends(get_user)):
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required"
        )

    return user


def get_device(
    authorization: Optional[str] = Header(None)
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing device token"
        )

    token = authorization.split(" ", 1)[1]

    result = (
        supabase.table("devices")
        .select("*")
        .eq("device_token_hash", hash_token(token))
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=401,
            detail="Invalid device credentials"
        )

    return result.data[0]


# --------------------------------------------------
# REQUEST MODELS
# --------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class EnrollmentRequest(BaseModel):
    code: str
    hostname: str
    os_name: str
    agent_version: str


class MetricsRequest(BaseModel):
    cpu_percent: Optional[float] = Field(None, ge=0, le=100)
    ram_percent: Optional[float] = Field(None, ge=0, le=100)
    ram_used_mb: Optional[float] = Field(None, ge=0)
    disk_percent: Optional[float] = Field(None, ge=0, le=100)
    disk_used_gb: Optional[float] = Field(None, ge=0)
    battery_percent: Optional[float] = Field(None, ge=0, le=100)
    battery_plugged_in: Optional[bool] = None
    uptime_seconds: Optional[int] = Field(None, ge=0)
    processes: Optional[list[dict]] = None


class PermissionResponse(BaseModel):
    request_id: str
    decision: str


class EnrollmentCodeRequest(BaseModel):
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class PolicyRequest(BaseModel):
    monitoring_enabled: bool
    permissions: dict[str, bool]


class PermissionRequestCreate(BaseModel):
    scope: str
    description: Optional[str] = None


# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------

@app.get("/")
def root():
    return {
        "application": "CloudMonitor",
        "status": "online",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    try:
        supabase.table("profiles").select("id").limit(1).execute()

        return {
            "status": "healthy",
            "database": "connected"
        }

    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )


# --------------------------------------------------
# AUTHENTICATION
# --------------------------------------------------

@app.post("/api/v1/auth/login")
def login(data: LoginRequest):

    try:
        # CloudMonitor login accepts an email address.
        result = supabase.auth.sign_in_with_password({
            "email": data.username,
            "password": data.password
        })

        if not result.session:
            raise HTTPException(
                status_code=401,
                detail="Authentication failed"
            )

        profile = get_profile(str(result.user.id))

        return {
            "access_token": result.session.access_token,
            "token_type": "bearer",
            "role": profile["role"]
        }

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )


# --------------------------------------------------
# ENROLLMENT CODE GENERATION
# --------------------------------------------------

@app.post("/api/v1/admin/enrollment-codes")
def create_enrollment_code(
    data: EnrollmentCodeRequest,
    admin=Depends(require_admin)
):

    code = secrets.token_urlsafe(24)

    expires = utc_now() + timedelta(
        hours=data.expires_in_hours
    )

    supabase.table("enrollment_codes").insert({
        "code_hash": hash_token(code),
        "created_by": admin["id"],
        "expires_at": expires.isoformat()
    }).execute()

    # Show the raw code only once.
    return {
        "enrollment_code": code,
        "expires_at": expires.isoformat()
    }


# --------------------------------------------------
# DEVICE ENROLLMENT
# --------------------------------------------------

@app.post("/api/v1/agent/enroll")
def enroll_device(
    data: EnrollmentRequest,
    user=Depends(get_user)
):

    code_result = (
        supabase.table("enrollment_codes")
        .select("*")
        .eq("code_hash", hash_token(data.code))
        .is_("used_at", "null")
        .execute()
    )

    if not code_result.data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or already used enrollment code"
        )

    enrollment = code_result.data[0]

    expires = datetime.fromisoformat(
        enrollment["expires_at"].replace("Z", "+00:00")
    )

    if expires <= utc_now():
        raise HTTPException(
            status_code=400,
            detail="Enrollment code expired"
        )

    device_token = secrets.token_urlsafe(48)

    result = supabase.table("devices").insert({
        "hostname": data.hostname,
        "os_name": data.os_name,
        "agent_version": data.agent_version,
        "device_token_hash": hash_token(device_token),
        "monitoring_enabled": False,
        "permissions": {
            "system_metrics": False,
            "disk_metrics": False,
            "battery_metrics": False,
            "uptime_metrics": False,
            "process_metadata": False
        }
    }).execute()

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Device registration failed"
        )

    device = result.data[0]

    # Mark the enrollment code as used.
    supabase.table("enrollment_codes").update({
        "used_at": utc_now().isoformat()
    }).eq("id", enrollment["id"]).is_(
        "used_at", "null"
    ).execute()

    return {
        "device_id": device["id"],
        "device_token": device_token
    }


# --------------------------------------------------
# DEVICE POLICY
# --------------------------------------------------

@app.get("/api/v1/agent/policy")
def get_policy(device=Depends(get_device)):

    return {
        "monitoring_enabled": device["monitoring_enabled"],
        "permissions": device["permissions"]
    }


@app.put("/api/v1/admin/devices/{device_id}/policy")
def update_policy(
    device_id: str,
    data: PolicyRequest,
    admin=Depends(require_admin)
):

    result = supabase.table("devices").update({
        "monitoring_enabled": data.monitoring_enabled,
        "permissions": data.permissions
    }).eq("id", device_id).execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    return {"message": "Device policy updated"}


# --------------------------------------------------
# METRICS COLLECTION
# --------------------------------------------------

@app.post("/api/v1/agent/heartbeat")
def heartbeat(
    data: MetricsRequest,
    device=Depends(get_device)
):

    if not device["monitoring_enabled"]:
        raise HTTPException(
            status_code=403,
            detail="Monitoring is disabled"
        )

    metrics = data.model_dump(exclude_none=True)
    permissions = device["permissions"]

    allowed = {
        "system_metrics": [
            "cpu_percent",
            "ram_percent",
            "ram_used_mb"
        ],
        "disk_metrics": [
            "disk_percent",
            "disk_used_gb"
        ],
        "battery_metrics": [
            "battery_percent",
            "battery_plugged_in"
        ],
        "uptime_metrics": [
            "uptime_seconds"
        ],
        "process_metadata": [
            "processes"
        ]
    }

    # Enforce permissions on the server too.
    permitted_metrics = {}

    for scope, fields in allowed.items():
        if permissions.get(scope, False):
            for field in fields:
                if field in metrics:
                    permitted_metrics[field] = metrics[field]

    if not permitted_metrics:
        raise HTTPException(
            status_code=403,
            detail="No authorized metrics supplied"
        )

    supabase.table("metrics").insert({
        "device_id": device["id"],
        "metrics": permitted_metrics
    }).execute()

    supabase.table("devices").update({
        "last_seen": utc_now().isoformat()
    }).eq("id", device["id"]).execute()

    # Generate basic monitoring alerts.
    if permitted_metrics.get("cpu_percent", 0) >= 90:
        create_alert(
            device["id"],
            "high_cpu",
            "CPU usage exceeded 90%",
            "critical"
        )

    if permitted_metrics.get("ram_percent", 0) >= 90:
        create_alert(
            device["id"],
            "high_memory",
            "RAM usage exceeded 90%",
            "warning"
        )

    return {
        "success": True,
        "message": "Metrics synchronized"
    }


def create_alert(device_id, alert_type, message, severity):

    supabase.table("alerts").insert({
        "device_id": device_id,
        "alert_type": alert_type,
        "message": message,
        "severity": severity
    }).execute()


# --------------------------------------------------
# PERMISSION REQUESTS
# --------------------------------------------------

@app.get("/api/v1/agent/permission-requests")
def get_permission_requests(device=Depends(get_device)):

    result = (
        supabase.table("permission_requests")
        .select("*")
        .eq("device_id", device["id"])
        .eq("status", "pending")
        .execute()
    )

    return {
        "requests": result.data
    }


@app.post("/api/v1/agent/permission-responses")
def respond_to_permission(
    data: PermissionResponse,
    device=Depends(get_device)
):

    if data.decision not in ["approved", "denied"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid permission decision"
        )

    result = (
        supabase.table("permission_requests")
        .update({
            "status": data.decision,
            "responded_at": utc_now().isoformat()
        })
        .eq("id", data.request_id)
        .eq("device_id", device["id"])
        .eq("status", "pending")
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Pending permission request not found"
        )

    # Apply approved permission to the device.
    if data.decision == "approved":
        current = device["permissions"].copy()

        # Retrieve the approved scope from the request.
        request = result.data[0]

        scope = request["scope"]

        if scope not in current:
            raise HTTPException(
                status_code=400,
                detail="Unknown permission scope"
            )

        current[scope] = True

        supabase.table("devices").update({
            "permissions": current
        }).eq("id", device["id"]).execute()

    return {
        "message": f"Permission {data.decision}"
    }


@app.post("/api/v1/admin/devices/{device_id}/permission-requests")
def create_permission_request(
    device_id: str,
    data: PermissionRequestCreate,
    admin=Depends(require_admin)
):

    valid_scopes = [
        "system_metrics",
        "disk_metrics",
        "battery_metrics",
        "uptime_metrics",
        "process_metadata"
    ]

    if data.scope not in valid_scopes:
        raise HTTPException(
            status_code=400,
            detail="Unknown permission scope"
        )

    device = (
        supabase.table("devices")
        .select("id")
        .eq("id", device_id)
        .execute()
    )

    if not device.data:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    result = supabase.table("permission_requests").insert({
        "device_id": device_id,
        "scope": data.scope,
        "description": data.description or data.scope
    }).execute()

    return {
        "message": "Permission request created",
        "request": result.data[0]
    }


# --------------------------------------------------
# ADMIN DASHBOARD DATA
# --------------------------------------------------

@app.get("/api/v1/admin/devices")
def list_devices(admin=Depends(require_admin)):

    result = (
        supabase.table("devices")
        .select(
            "id,hostname,os_name,agent_version,"
            "monitoring_enabled,permissions,last_seen,created_at"
        )
        .order("created_at", desc=True)
        .execute()
    )

    return {"devices": result.data}


@app.get("/api/v1/admin/metrics/{device_id}")
def get_device_metrics(
    device_id: str,
    admin=Depends(require_admin)
):

    result = (
        supabase.table("metrics")
        .select("*")
        .eq("device_id", device_id)
        .order("recorded_at", desc=True)
        .limit(100)
        .execute()
    )

    return {"metrics": result.data}


@app.get("/api/v1/admin/alerts")
def get_alerts(admin=Depends(require_admin)):

    result = (
        supabase.table("alerts")
        .select("*")
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )

    return {"alerts": result.data}
