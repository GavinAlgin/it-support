import os
import hashlib
import secrets
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client

app = FastAPI(title="CloudMonitor Central Control System", version="1.3.0")

# Configure CORS for frontend access (Admin web dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase Client
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://ddfapzvvniqameddqspf.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRkZmFwenZ2bmlxYW1lZGRxc3BmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjQ1NjA3MzgsImV4cCI6MjA4MDEzNjczOH0.p-6du8uSJQ4YsIxoXQo7MGSuvTI79JGUy7CcUUE8JRI")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Helper function to hash secrets/tokens
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

# ==========================================
# PYDANTIC SCHEMAS
# ==========================================

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class ConnectionRequestPayload(BaseModel):
    device_id: str
    hostname: str
    display_name: Optional[str] = None
    os_name: Optional[str] = None
    agent_version: Optional[str] = None
    organisation: Optional[str] = None
    user_email: Optional[str] = None
    claim_secret: str

class MetricsPayload(BaseModel):
    metrics: Dict[str, Any]

# ==========================================
# AUTHENTICATION & ENROLLMENT ENDPOINTS
# ==========================================

@app.post("/api/v1/auth/login")
def login(credentials: UserLogin):
    """Authenticate administrators or users against Supabase Auth and check admin_users table."""
    try:
        res = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        user = res.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid login credentials")

        # Optional: Verify if user is registered in public.admin_users
        admin_check = supabase.table("admin_users").select("*").eq("user_id", user.id).execute()
        is_admin = len(admin_check.data) > 0

        return {
            "success": True,
            "is_admin": is_admin,
            "session": res.session.dict() if res.session else None,
            "user": user.dict()
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(exc)}"
        )

@app.post("/api/v1/agents/request-connection")
def request_connection(payload: ConnectionRequestPayload):
    """
    Step 1 of Agent Enrollment: Agent submits a connection request with a claim secret.
    The secret is hashed before storing in connection_requests.
    """
    try:
        request_id = str(uuid.uuid4())
        secret_hash = hash_token(payload.claim_secret)

        data = {
            "id": request_id,
            "device_id": payload.device_id,
            "hostname": payload.hostname,
            "display_name": payload.display_name,
            "os_name": payload.os_name,
            "agent_version": payload.agent_version,
            "organisation": payload.organisation,
            "user_email": payload.user_email,
            "claim_secret_hash": secret_hash,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        supabase.table("connection_requests").insert(data).execute()
        return {"success": True, "message": "Connection request submitted, waiting for admin approval.", "request_id": request_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to submit connection request: {str(exc)}")

@app.post("/api/v1/agents/claim")
def claim_agent_token(request_id: str, claim_secret: str):
    """
    Step 2: Once approved by an admin, the agent exchanges its claim secret 
    to receive its permanent api_token (stored as a hash in agents table).
    """
    try:
        # Fetch connection request
        req_res = supabase.table("connection_requests").select("*").eq("id", request_id).single().execute()
        req_data = req_res.data
        
        if not req_data or req_data["status"] != "approved":
            raise HTTPException(status_code=400, detail="Request is not approved or does not exist.")

        # Verify claim secret
        if hash_token(claim_secret) != req_data["claim_secret_hash"]:
            raise HTTPException(status_code=403, detail="Invalid claim secret.")

        # Generate permanent agent token
        raw_agent_token = secrets.token_urlsafe(32)
        token_hash = hash_token(raw_agent_token)
        agent_id = str(uuid.uuid4())

        # Create agent record in public.agents
        agent_payload = {
            "id": agent_id,
            "device_id": req_data["device_id"],
            "hostname": req_data["hostname"],
            "display_name": req_data["display_name"],
            "os_name": req_data["os_name"],
            "agent_version": req_data["agent_version"],
            "organisation": req_data["organisation"],
            "user_email": req_data["user_email"],
            "api_token_hash": token_hash,
            "status": "approved",
            "approved_by": req_data.get("approved_by"),
            "approved_at": req_data.get("approved_at"),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("agents").insert(agent_payload).execute()

        # Update connection request reference
        supabase.table("connection_requests").update({
            "agent_id": agent_id,
            "claimed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", request_id).execute()

        return {"success": True, "agent_id": agent_id, "api_token": raw_agent_token}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Claim failed: {str(exc)}")

# ==========================================
# TELEMETRY ENDPOINT
# ==========================================

@app.post("/api/v1/telemetry")
def receive_telemetry(payload: MetricsPayload, authorization: Optional[str] = Header(None)):
    """Receive system metrics from an authenticated agent and store in public.telemetry."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header.")
    
    raw_token = authorization.removeprefix("Bearer ").strip()
    token_hash = hash_token(raw_token)

    try:
        # Verify agent by token hash
        # agent_res = supabase.table("agents").select("id, status").eq("api_token_hash", token_hash).single().execute()
        # agent = agent_res.data

        
            agent_res = (
                supabase.table("agents")
                .select("id, status")
                .eq("api_token_hash", token_hash)
                .execute()
            )

            if not agent_res.data:
                raise HTTPException(
                    status_code=403,
                    detail="Agent token not found or invalid."
                )

            if len(agent_res.data) > 1:
                raise HTTPException(
                    status_code=500,
                    detail="Multiple agents have the same API token hash."
                )

            agent = agent_res.data[0]

            if agent["status"] != "approved":
                raise HTTPException(
                    status_code=403,
                    detail="Agent is not approved."
                )

            agent_id = agent["id"]


        if not agent or agent["status"] != "approved":
            raise HTTPException(status_code=403, detail="Agent token invalid or revoked.")

        agent_id = agent["id"]

        # Insert telemetry payload into JSONB column
        telemetry_data = {
            "agent_id": agent_id,
            "metrics": payload.metrics,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        supabase.table("telemetry").insert(telemetry_data).execute()

        # Update last_seen timestamp in agents table
        supabase.table("agents").update({
            "last_seen": datetime.now(timezone.utc).isoformat()
        }).eq("id", agent_id).execute()

        return {"success": True, "message": "Telemetry recorded successfully."}
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to record telemetry: {str(exc)}")

# ==========================================
# ADMIN DASHBOARD ENDPOINTS
# ==========================================

@app.get("/api/v1/admin/agents")
def get_all_agents():
    """Retrieve all agents for the admin dashboard."""
    try:
        res = supabase.table("agents").select("*").execute()
        return {"agents": res.data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch agents: {str(exc)}")

@app.get("/api/v1/admin/connection-requests")
def get_connection_requests():
    """Retrieve pending connection requests for admin review."""
    try:
        res = supabase.table("connection_requests").select("*").eq("status", "pending").execute()
        return {"requests": res.data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch connection requests: {str(exc)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)