# import os
# import hashlib
# import secrets
# import uuid
# from typing import Optional, Dict, Any, List
# from datetime import datetime, timezone
# from fastapi import FastAPI, HTTPException, Header, status
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, EmailStr
# from supabase import create_client, Client

# app = FastAPI(title="CloudMonitor Central Control System", version="1.3.0")

# # Configure CORS for frontend access (Admin web dashboard)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Initialize Supabase Client
# SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ddfapzvvniqameddqspf.supabase.co")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRkZmFwenZ2bmlxYW1lZGRxc3BmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1NjA3MzgsImV4cCI6MjA4MDEzNjczOH0.p-6du8uSJQ4YsIxoXQo7MGSuvTI79JGUy7CcUUE8JRI")
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# # Helper function to hash secrets/tokens
# def hash_token(token: str) -> str:
#     return hashlib.sha256(token.encode("utf-8")).hexdigest()

# # ==========================================
# # PYDANTIC SCHEMAS
# # ==========================================

# class UserLogin(BaseModel):
#     email: EmailStr
#     password: str

# class ConnectionRequestPayload(BaseModel):
#     device_id: str
#     hostname: str
#     display_name: Optional[str] = None
#     os_name: Optional[str] = None
#     agent_version: Optional[str] = None
#     organisation: Optional[str] = None
#     user_email: Optional[str] = None
#     claim_secret: str

# class MetricsPayload(BaseModel):
#     metrics: Dict[str, Any]

# # ==========================================
# # AUTHENTICATION & ENROLLMENT ENDPOINTS
# # ==========================================

# @app.post("/api/v1/auth/login")
# def login(credentials: UserLogin):
#     """Authenticate administrators or users against Supabase Auth and check admin_users table."""
#     try:
#         res = supabase.auth.sign_in_with_password({
#             "email": credentials.email,
#             "password": credentials.password
#         })
        
#         user = res.user
#         if not user:
#             raise HTTPException(status_code=401, detail="Invalid login credentials")

#         # Optional: Verify if user is registered in public.admin_users
#         admin_check = supabase.table("admin_users").select("*").eq("user_id", user.id).execute()
#         is_admin = len(admin_check.data) > 0

#         return {
#             "success": True,
#             "is_admin": is_admin,
#             "session": res.session.dict() if res.session else None,
#             "user": user.dict()
#         }
#     except Exception as exc:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Authentication failed: {str(exc)}"
#         )

# @app.post("/api/v1/agents/request-connection")
# def request_connection(payload: ConnectionRequestPayload):
#     """
#     Step 1 of Agent Enrollment: Agent submits a connection request with a claim secret.
#     The secret is hashed before storing in connection_requests.
#     """
#     try:
#         request_id = str(uuid.uuid4())
#         secret_hash = hash_token(payload.claim_secret)

#         data = {
#             "id": request_id,
#             "device_id": payload.device_id,
#             "hostname": payload.hostname,
#             "display_name": payload.display_name,
#             "os_name": payload.os_name,
#             "agent_version": payload.agent_version,
#             "organisation": payload.organisation,
#             "user_email": payload.user_email,
#             "claim_secret_hash": secret_hash,
#             "status": "pending",
#             "created_at": datetime.now(timezone.utc).isoformat()
#         }

#         supabase.table("connection_requests").insert(data).execute()
#         return {"success": True, "message": "Connection request submitted, waiting for admin approval.", "request_id": request_id}
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=f"Failed to submit connection request: {str(exc)}")

# @app.post("/api/v1/agents/claim")
# def claim_agent_token(request_id: str, claim_secret: str):
#     """
#     Step 2: Once approved by an admin, the agent exchanges its claim secret 
#     to receive its permanent api_token (stored as a hash in agents table).
#     """
#     try:
#         # Fetch connection request
#         req_res = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute()
#         req_data = req_res.data
        
#         if not req_data or req_data["status"] != "approved":
#             raise HTTPException(status_code=400, detail="Request is not approved or does not exist.")

#         # Verify claim secret
#         if hash_token(claim_secret) != req_data["claim_secret_hash"]:
#             raise HTTPException(status_code=403, detail="Invalid claim secret.")

#         # Generate permanent agent token
#         raw_agent_token = secrets.token_urlsafe(32)
#         token_hash = hash_token(raw_agent_token)
#         agent_id = str(uuid.uuid4())

#         # Create agent record in public.agents
#         agent_payload = {
#             "id": agent_id,
#             "device_id": req_data["device_id"],
#             "hostname": req_data["hostname"],
#             "display_name": req_data["display_name"],
#             "os_name": req_data["os_name"],
#             "agent_version": req_data["agent_version"],
#             "organisation": req_data["organisation"],
#             "user_email": req_data["user_email"],
#             "api_token_hash": token_hash,
#             "status": "approved",
#             "approved_by": req_data.get("approved_by"),
#             "approved_at": req_data.get("approved_at"),
#             "created_at": datetime.now(timezone.utc).isoformat()
#         }
#         supabase.table("agents").insert(agent_payload).execute()

#         # Update connection request reference
#         supabase.table("connection_requests").update({
#             "agent_id": agent_id,
#             "claimed_at": datetime.now(timezone.utc).isoformat()
#         }).eq("id", request_id).execute()

#         return {"success": True, "agent_id": agent_id, "api_token": raw_agent_token}
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=f"Claim failed: {str(exc)}")

# # ==========================================
# # TELEMETRY ENDPOINT
# # ==========================================


# @app.post("/api/v1/telemetry")
# def receive_telemetry(
#     payload: MetricsPayload,
#     authorization: Optional[str] = Header(None)
# ):
#     """Receive system metrics from an authenticated agent."""

#     if not authorization or not authorization.startswith("Bearer "):
#         raise HTTPException(
#             status_code=401,
#             detail="Missing or invalid authorization header."
#         )

#     raw_token = authorization.removeprefix("Bearer ").strip()
#     token_hash = hash_token(raw_token)

#     try:
#         # Verify agent using the hashed API token
#         agent_res = (
#             supabase.table("agents")
#             .select("id, status")
#             .eq("api_token_hash", token_hash)
#             .execute()
#         )

#         # Check if agent exists
#         if not agent_res.data:
#             raise HTTPException(
#                 status_code=403,
#                 detail="Agent token not found or invalid."
#             )

#         # Ensure only one agent matches the token
#         if len(agent_res.data) > 1:
#             raise HTTPException(
#                 status_code=500,
#                 detail="Multiple agents have the same API token hash."
#             )

#         agent = agent_res.data[0]

#         # Check agent approval status
#         if agent["status"] != "approved":
#             raise HTTPException(
#                 status_code=403,
#                 detail="Agent is not approved."
#             )

#         agent_id = agent["id"]

#         # Insert telemetry data
#         telemetry_data = {
#             "agent_id": agent_id,
#             "metrics": payload.metrics,
#             "created_at": datetime.now(timezone.utc).isoformat()
#         }

#         supabase.table("telemetry").insert(telemetry_data).execute()

#         # Update agent last_seen timestamp
#         supabase.table("agents").update({
#             "last_seen": datetime.now(timezone.utc).isoformat()
#         }).eq("id", agent_id).execute()

#         return {
#             "success": True,
#             "message": "Telemetry recorded successfully."
#         }

#     except HTTPException:
#         raise

#     except Exception as exc:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to record telemetry: {str(exc)}"
#         )

# # ==========================================
# # ADMIN DASHBOARD ENDPOINTS
# # ==========================================

# @app.get("/api/v1/admin/agents")
# def get_all_agents():
#     """Retrieve all agents for the admin dashboard."""
#     try:
#         res = supabase.table("agents").select("*").execute()
#         return {"agents": res.data}
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch agents: {str(exc)}")

# @app.get("/api/v1/admin/connection-requests")
# def get_connection_requests():
#     """Retrieve pending connection requests for admin review."""
#     try:
#         res = supabase.table("connection_requests").select("*").eq("status", "pending").execute()
#         return {"requests": res.data}
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=f"Failed to fetch connection requests: {str(exc)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

import hashlib
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from supabase import Client, create_client


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
# SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", os.getenv("SUPABASE_KEY", "")).strip()
# SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ddfapzvvniqameddqspf.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRkZmFwenZ2bmlxYW1lZGRxc3BmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1NjA3MzgsImV4cCI6MjA4MDEzNjczOH0.p-6du8uSJQ4YsIxoXQo7MGSuvTI79JGUy7CcUUE8JRI")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRkZmFwenZ2bmlxYW1lZGRxc3BmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1NjA3MzgsImV4cCI6MjA4MDEzNjczOH0.p-6du8uSJQ4YsIxoXQo7MGSuvTI79JGUy7CcUUE8JRI")

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise RuntimeError("Set SUPABASE_URL and SUPABASE_ANON_KEY before starting CloudMonitor.")

# The service-role client is restricted to this backend. It bypasses RLS, so
# every operation using it is validated in the API before touching the database.
public_supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
service_supabase: Optional[Client] = (
    create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    if SUPABASE_SERVICE_ROLE_KEY else None
)

app = FastAPI(
    title="CloudMonitor Central Control System",
    description="Central API for CloudMonitor desktop agents, telemetry and support tickets.",
    version="1.4.0",
)

allowed_origins = [
    item.strip()
    for item in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    ).split(",")
    if item.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_service_client() -> Client:
    if service_supabase is None:
        raise HTTPException(
            status_code=503,
            detail="Agent operations are not configured. Set SUPABASE_SERVICE_ROLE_KEY on the backend.",
        )
    return service_supabase


def bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header is required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="A valid Bearer token is required.")
    return token.strip()


def authenticated_user(authorization: Optional[str]):
    """Validate a Supabase access token and return user-scoped DB client."""
    token = bearer_token(authorization)
    try:
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        client.postgrest.auth(token)
        result = client.auth.get_user(token)
        user = getattr(result, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="Session is invalid or expired.")
        return user, client, token
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Session is invalid or expired.")


def require_admin(authorization: Optional[str]):
    user, client, token = authenticated_user(authorization)
    try:
        membership = (
            client.table("admin_users")
            .select("user_id")
            .eq("user_id", user.id)
            .limit(1)
            .execute()
        )
        if not membership.data:
            raise HTTPException(status_code=403, detail="Administrator access is required.")
        return user, client, token
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=403,
            detail="Could not verify administrator membership. Check admin_users RLS policies.",
        ) from exc


def safe_user(user) -> dict:
    metadata = getattr(user, "user_metadata", None) or {}
    return {
        "id": user.id,
        "email": getattr(user, "email", None),
        "name": metadata.get("full_name") or metadata.get("name") or metadata.get("display_name"),
    }


def ticket_reference() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    suffix = secrets.token_hex(3).upper()
    return f"CM-{stamp}-{suffix}"


# -----------------------------------------------------------------------------
# Request schemas
# -----------------------------------------------------------------------------

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ConnectionRequestPayload(BaseModel):
    device_id: str = Field(min_length=1, max_length=128)
    hostname: str = Field(min_length=1, max_length=255)
    display_name: Optional[str] = Field(default=None, max_length=255)
    os_name: Optional[str] = Field(default=None, max_length=255)
    agent_version: Optional[str] = Field(default=None, max_length=40)
    organisation: Optional[str] = Field(default=None, max_length=255)
    user_email: Optional[EmailStr] = None
    claim_secret: str = Field(min_length=20, max_length=256)


class MetricsPayload(BaseModel):
    metrics: Dict[str, Any]


class TicketPayload(BaseModel):
    subject: str = Field(min_length=3, max_length=180)
    category: str = Field(min_length=2, max_length=80)
    priority: str = Field(default="normal", max_length=20)
    description: str = Field(min_length=10, max_length=10000)
    device_id: Optional[str] = Field(default=None, max_length=128)
    hostname: Optional[str] = Field(default=None, max_length=255)
    device_name: Optional[str] = Field(default=None, max_length=255)
    os_name: Optional[str] = Field(default=None, max_length=255)
    agent_version: Optional[str] = Field(default=None, max_length=40)


class TicketStatusUpdate(BaseModel):
    status: str = Field(min_length=2, max_length=30)


class ConnectionRequestDecision(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")


# -----------------------------------------------------------------------------
# Health and authentication
# -----------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "online", "service": "CloudMonitor API", "version": app.version}


@app.post("/api/v1/auth/login")
def login(credentials: UserLogin):
    """Login for the desktop agent and dashboard. Returns access_token at top level."""
    try:
        result = public_supabase.auth.sign_in_with_password(
            {"email": str(credentials.email), "password": credentials.password}
        )
        user = getattr(result, "user", None)
        session = getattr(result, "session", None)
        if not user or not session or not getattr(session, "access_token", None):
            raise HTTPException(status_code=401, detail="Invalid login credentials.")

        # Use a separate user-scoped client for the membership lookup.
        user_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        user_client.postgrest.auth(session.access_token)
        try:
            admin_result = (
                user_client.table("admin_users")
                .select("user_id")
                .eq("user_id", user.id)
                .limit(1)
                .execute()
            )
            is_admin = bool(admin_result.data)
        except Exception:
            # Login remains valid for a non-admin user if membership cannot be read.
            is_admin = False

        return {
            "success": True,
            "access_token": session.access_token,
            "token_type": "bearer",
            "expires_in": getattr(session, "expires_in", None),
            "is_admin": is_admin,
            "user": safe_user(user),
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Authentication failed. Check your email and password.")


# -----------------------------------------------------------------------------
# Agent enrollment
# -----------------------------------------------------------------------------

@app.post("/api/v1/agents/request-connection")
def request_connection(payload: ConnectionRequestPayload):
    """Create a pending enrollment request. The claim secret is stored only as a hash."""
    db = get_service_client()
    request_id = str(uuid.uuid4())
    data = {
        "id": request_id,
        "device_id": payload.device_id,
        "hostname": payload.hostname,
        "display_name": payload.display_name,
        "os_name": payload.os_name,
        "agent_version": payload.agent_version,
        "organisation": payload.organisation,
        "user_email": str(payload.user_email) if payload.user_email else None,
        "claim_secret_hash": hash_token(payload.claim_secret),
        "status": "pending",
        "created_at": utc_now(),
    }
    try:
        db.table("connection_requests").insert(data).execute()
        return {
            "success": True,
            "message": "Connection request submitted and awaiting administrator approval.",
            "request_id": request_id,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to submit connection request.") from exc


@app.post("/api/v1/agents/claim")
def claim_agent_token(request_id: str = Query(...), claim_secret: str = Query(..., min_length=20)):
    """Exchange an approved request and its claim secret for an agent API token."""
    db = get_service_client()
    try:
        request_result = (
            db.table("connection_requests")
            .select("*")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        if not request_result.data:
            raise HTTPException(status_code=404, detail="Connection request was not found.")
        request_data = request_result.data[0]
        if request_data.get("status") != "approved":
            raise HTTPException(status_code=400, detail="Connection request has not been approved.")
        if not secrets.compare_digest(
            hash_token(claim_secret), str(request_data.get("claim_secret_hash", ""))
        ):
            raise HTTPException(status_code=403, detail="Invalid claim secret.")
        if request_data.get("agent_id"):
            raise HTTPException(status_code=409, detail="This connection request has already been claimed.")

        raw_token = secrets.token_urlsafe(48)
        agent_id = str(uuid.uuid4())
        now = utc_now()
        agent_data = {
            "id": agent_id,
            "device_id": request_data["device_id"],
            "hostname": request_data["hostname"],
            "display_name": request_data.get("display_name"),
            "os_name": request_data.get("os_name"),
            "agent_version": request_data.get("agent_version"),
            "organisation": request_data.get("organisation"),
            "user_email": request_data.get("user_email"),
            "api_token_hash": hash_token(raw_token),
            "status": "approved",
            "approved_by": request_data.get("approved_by"),
            "approved_at": request_data.get("approved_at") or now,
            "created_at": now,
        }
        db.table("agents").insert(agent_data).execute()
        db.table("connection_requests").update(
            {"agent_id": agent_id, "claimed_at": now}
        ).eq("id", request_id).execute()
        return {"success": True, "agent_id": agent_id, "api_token": raw_token}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Agent claim failed.") from exc


# -----------------------------------------------------------------------------
# Agent telemetry
# -----------------------------------------------------------------------------

@app.post("/api/v1/telemetry")
def receive_telemetry(
    payload: MetricsPayload,
    authorization: Optional[str] = Header(default=None),
):
    db = get_service_client()
    raw_token = bearer_token(authorization)
    token_digest = hash_token(raw_token)
    try:
        result = (
            db.table("agents")
            .select("id,status")
            .eq("api_token_hash", token_digest)
            .limit(2)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=401, detail="Agent token is invalid.")
        if len(result.data) != 1:
            raise HTTPException(status_code=409, detail="Agent token is not unique.")
        agent = result.data[0]
        if agent.get("status") != "approved":
            raise HTTPException(status_code=403, detail="Agent is not approved.")

        now = utc_now()
        db.table("telemetry").insert(
            {"agent_id": agent["id"], "metrics": payload.metrics, "created_at": now}
        ).execute()
        db.table("agents").update({"last_seen": now}).eq("id", agent["id"]).execute()
        return {"success": True, "message": "Telemetry recorded successfully."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to record telemetry.") from exc


# -----------------------------------------------------------------------------
# User support tickets
# -----------------------------------------------------------------------------

@app.post("/api/v1/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketPayload,
    authorization: Optional[str] = Header(default=None),
):
    user, client, _ = authenticated_user(authorization)
    priority = payload.priority.strip().lower()
    if priority not in {"low", "normal", "high", "urgent"}:
        raise HTTPException(status_code=422, detail="Priority must be low, normal, high or urgent.")

    now = utc_now()
    row = {
        "ticket_number": ticket_reference(),
        "user_id": user.id,
        "user_email": getattr(user, "email", None),
        "subject": payload.subject.strip(),
        "category": payload.category.strip(),
        "priority": priority,
        "description": payload.description.strip(),
        "device_id": payload.device_id,
        "hostname": payload.hostname,
        "device_name": payload.device_name,
        "os_name": payload.os_name,
        "agent_version": payload.agent_version,
        "status": "open",
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = client.table("tickets").insert(row).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Ticket could not be created.")
        ticket = result.data[0]
        return {
            "success": True,
            "message": "Support ticket submitted successfully.",
            "ticket": {
                "id": ticket.get("id"),
                "ticket_number": ticket.get("ticket_number"),
                "subject": ticket.get("subject"),
                "category": ticket.get("category"),
                "priority": ticket.get("priority"),
                "status": ticket.get("status"),
                "created_at": ticket.get("created_at"),
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to submit support ticket.") from exc


@app.get("/api/v1/tickets")
def get_my_tickets(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    user, client, _ = authenticated_user(authorization)
    try:
        result = (
            client.table("tickets")
            .select("id,ticket_number,subject,category,priority,description,status,created_at,updated_at")
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"success": True, "tickets": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to retrieve your tickets.") from exc


# -----------------------------------------------------------------------------
# Administrator endpoints
# -----------------------------------------------------------------------------

@app.get("/api/v1/admin/agents")
def get_all_agents(authorization: Optional[str] = Header(default=None)):
    _, client, _ = require_admin(authorization)
    db = get_service_client()
    try:
        result = (
            db.table("agents")
            .select("id,device_id,hostname,display_name,os_name,agent_version,organisation,user_email,status,last_seen,approved_at,created_at")
            .order("created_at", desc=True)
            .execute()
        )
        return {"success": True, "agents": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch agents.") from exc


@app.get("/api/v1/admin/connection-requests")
def get_connection_requests(authorization: Optional[str] = Header(default=None)):
    require_admin(authorization)
    db = get_service_client()
    try:
        result = (
            db.table("connection_requests")
            .select("id,device_id,hostname,display_name,os_name,agent_version,organisation,user_email,status,created_at,approved_at,approved_by,agent_id,claimed_at")
            .eq("status", "pending")
            .order("created_at", desc=True)
            .execute()
        )
        return {"success": True, "requests": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch connection requests.") from exc


@app.patch("/api/v1/admin/connection-requests/{request_id}")
def decide_connection_request(
    request_id: str,
    payload: ConnectionRequestDecision,
    authorization: Optional[str] = Header(default=None),
):
    admin, _, _ = require_admin(authorization)
    db = get_service_client()
    try:
        existing = (
            db.table("connection_requests")
            .select("id,status")
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            raise HTTPException(status_code=404, detail="Connection request not found.")
        if existing.data[0].get("status") != "pending":
            raise HTTPException(status_code=409, detail="This request has already been processed.")
        now = utc_now()
        updated = {
            "status": payload.status,
            "approved_by": admin.id if payload.status == "approved" else None,
            "approved_at": now if payload.status == "approved" else None,
        }
        db.table("connection_requests").update(updated).eq("id", request_id).execute()
        return {"success": True, "message": f"Connection request {payload.status}.", "request_id": request_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to update connection request.") from exc


@app.get("/api/v1/admin/tickets")
def get_all_tickets(
    authorization: Optional[str] = Header(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    ticket_status: Optional[str] = Query(default=None, alias="status"),
):
    require_admin(authorization)
    db = get_service_client()
    try:
        query = (
            db.table("tickets")
            .select("id,ticket_number,user_id,user_email,subject,category,priority,description,device_id,hostname,device_name,os_name,agent_version,status,created_at,updated_at")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if ticket_status:
            query = query.eq("status", ticket_status)
        result = query.execute()
        return {"success": True, "tickets": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to fetch support tickets.") from exc


@app.patch("/api/v1/admin/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    authorization: Optional[str] = Header(default=None),
):
    require_admin(authorization)
    allowed = {"open", "in_progress", "pending", "resolved", "closed"}
    new_status = payload.status.strip().lower()
    if new_status not in allowed:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(sorted(allowed))}.")
    db = get_service_client()
    try:
        result = (
            db.table("tickets")
            .update({"status": new_status, "updated_at": utc_now()})
            .eq("id", ticket_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        return {"success": True, "ticket": result.data[0]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to update ticket status.") from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
