import os
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client

app = FastAPI()

# ---------- CORS ----------

origins = [
    "https://courtsandrallies.netlify.app",
    "https://9aro.github.io",
    "https://9aro.github.io/courts-and-rallies/",
    "https://9aro.github.io/courts-and-rallies",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Config ----------

ADMIN_TOOLS_PASSCODE = "pickleball"  # tools/admin panel passcode

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set as environment variables."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------- Models ----------

class SessionCreate(BaseModel):
    name: str
    admin_passcode: str

class Session(BaseModel):
    id: str
    name: str
    admin_passcode: str

class Match(BaseModel):
    round: int
    court: int
    team1: List[str]
    team2: List[str]
    winner: Optional[str] = None  # "team1", "team2", or None

class TeamState(BaseModel):
    name: str
    players: List[str]

class SessionState(BaseModel):
    team1: TeamState
    team2: TeamState
    games_per_player: int
    rounds: int
    matches: List[Match]
    team1_score: int
    team2_score: int

class HostLoginBody(BaseModel):
    admin_passcode: str

class AdminToolsLoginBody(BaseModel):
    tools_passcode: str

# ---------- Basic routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}

# ---------- Sessions ----------

@app.post("/sessions", response_model=Session)
def create_session(body: SessionCreate):
    """
    Create a new session with a name and admin passcode.
    Stored permanently in Supabase (sessions table).
    """
    session_id = str(uuid.uuid4())
    row = {
        "id": session_id,
        "name": body.name,
        "admin_passcode": body.admin_passcode,
    }
    res = supabase.table("sessions").insert(row).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Could not create session")
    return Session(**res.data[0])


@app.get("/sessions", response_model=List[Session])
def list_sessions():
    """
    List all sessions stored in Supabase.
    """
    res = (
        supabase.table("sessions")
        .select("id,name,admin_passcode")
        .order("created_at", desc=True)
        .execute()
    )
    return [Session(**row) for row in res.data]


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    """
    Delete a session by ID. Its session_states row is removed
    automatically via the ON DELETE CASCADE foreign key.
    """
    res = supabase.table("sessions").delete().eq("id", session_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)

# ---------- Host login ----------

@app.post("/sessions/{session_id}/host-login", response_model=Session)
def host_login(session_id: str, body: HostLoginBody):
    """
    Verify the admin passcode for a session.
    """
    res = supabase.table("sessions").select("*").eq("id", session_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Session not found")

    session_row = res.data[0]
    if session_row["admin_passcode"] != body.admin_passcode:
        raise HTTPException(status_code=401, detail="Wrong admin passcode")

    return Session(**session_row)

# ---------- Admin tools login ----------

@app.post("/admin/tools-login")
def admin_tools_login(body: AdminToolsLoginBody):
    """
    Check tools/admin passcode for the local Admin panel.
    """
    if body.tools_passcode == ADMIN_TOOLS_PASSCODE:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong admin tools passcode")

# ---------- Session state (teams, fixtures, scores) ----------

@app.get("/sessions/{session_id}/state", response_model=SessionState)
def get_session_state(session_id: str):
    """
    Get full game state (teams, matches, scores) for a session,
    read from the session_states table in Supabase.
    """
    res = (
        supabase.table("session_states")
        .select("*")
        .eq("session_id", session_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Session state not found")

    row = res.data[0]
    return SessionState(
        team1=TeamState(name=row["team1_name"], players=row["team1_players"]),
        team2=TeamState(name=row["team2_name"], players=row["team2_players"]),
        games_per_player=row["games_per_player"],
        rounds=row["rounds"],
        matches=row["matches"],
        team1_score=row["team1_score"],
        team2_score=row["team2_score"],
    )


@app.put("/sessions/{session_id}/state", response_model=SessionState)
def put_session_state(session_id: str, state: SessionState):
    """
    Save or update full game state (teams, matches, scores) for a session.
    Upserts into the session_states table so this survives Render restarts.
    """
    exists = supabase.table("sessions").select("id").eq("id", session_id).execute()
    if not exists.data:
        raise HTTPException(status_code=404, detail="Session not found")

    row = {
        "session_id": session_id,
        "team1_name": state.team1.name,
        "team1_players": state.team1.players,
        "team2_name": state.team2.name,
        "team2_players": state.team2.players,
        "games_per_player": state.games_per_player,
        "rounds": state.rounds,
        "matches": [m.dict() for m in state.matches],
        "team1_score": state.team1_score,
        "team2_score": state.team2_score,
    }
    supabase.table("session_states").upsert(row).execute()
    return state
