from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from typing import List, Optional
import uuid

app = FastAPI()

# ---------- CORS ----------

origins = [
    # Old Netlify frontend (still allowed if you keep using it)
    # Old Netlify frontend (still allowed)
    "https://courtsandrallies.netlify.app",

    # New GitHub Pages frontend
    # GitHub Pages frontend
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

# ---------- Config / models ----------
# ---------- Config ----------

ADMIN_TOOLS_PASSCODE = "pickleball"  # tools/admin panel passcode

# ---------- Models ----------

class SessionCreate(BaseModel):
    name: str
    admin_passcode: str

class Session(BaseModel):
    id: str
    name: str
    admin_passcode: str  # stored so host can log back in

SESSIONS: List[Session] = []
class Match(BaseModel):
    round: int
    court: int
    team1: List[str]
    team2: List[str]
    winner: Optional[str]  # "team1", "team2", or None

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

# ---------- Routes ----------
# ---------- In-memory storage ----------

SESSIONS: List[Session] = []
SESSION_STATES: dict[str, SessionState] = {}

# ---------- Basic routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/sessions", response_model=Session)
def create_session(body: SessionCreate):
    """
    Create a new session with a name and admin passcode.
    Returns the session so the frontend can use id and name.
    """
    session_id = str(uuid.uuid4())
    session = Session(
        id=session_id,
        name=body.name,
        admin_passcode=body.admin_passcode
    )
    SESSIONS.append(session)
    # No state yet; frontend will create teams/fixtures and PUT /sessions/{id}/state
    return session

@app.get("/sessions", response_model=List[Session])
def list_sessions():
    """
    List all sessions currently in memory.
    """
    return SESSIONS

@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    """
    Delete a session by ID.

    Frontend calls:
    DELETE /sessions/<session_id>
    Delete a session by ID, and its stored state if present.
    """
    global SESSIONS

    # remove from sessions list
    for i, s in enumerate(SESSIONS):
        if s.id == session_id:
            del SESSIONS[i]
            return Response(status_code=204)
            break
    else:
        # no matching session
        raise HTTPException(status_code=404, detail="Session not found")

    raise HTTPException(status_code=404, detail="Session not found")
    # also remove any stored state
    if session_id in SESSION_STATES:
        del SESSION_STATES[session_id]

    return Response(status_code=204)

# ---------- Host login ----------

@app.post("/sessions/{session_id}/host-login", response_model=Session)
def host_login(session_id: str, body: HostLoginBody):
    """
    Verify the admin passcode for a session.

    Frontend calls (from Host existing session):
    Frontend calls (Host existing session):
    POST /sessions/<session_id>/host-login
    body: { "admin_passcode": "..." }
    """
    for s in SESSIONS:
        if s.id == session_id:
            if s.admin_passcode == body.admin_passcode:
                return s
            raise HTTPException(status_code=401, detail="Wrong admin passcode")
    raise HTTPException(status_code=404, detail="Session not found")

# ---------- Admin tools login ----------

@app.post("/admin/tools-login")
def admin_tools_login(body: AdminToolsLoginBody):
    """
    Check tools/admin passcode for local Admin panel.

    Frontend calls:
    POST /admin/tools-login
    body: { "tools_passcode": "..." }
    """
    if body.tools_passcode == ADMIN_TOOLS_PASSCODE:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong admin tools passcode")

# ---------- Session state (teams, fixtures, scores) ----------

@app.get("/sessions/{session_id}/state", response_model=SessionState)
def get_session_state(session_id: str):
    """
    Get full game state (teams, matches, scores) for a session.

    Used by host on any device to resume the ongoing fixtures.
    """
    if session_id not in SESSION_STATES:
        raise HTTPException(status_code=404, detail="Session state not found")
    return SESSION_STATES[session_id]

@app.put("/sessions/{session_id}/state", response_model=SessionState)
def put_session_state(session_id: str, state: SessionState):
    """
    Save or update full game state (teams, matches, scores) for a session.

    Frontend calls this:
      - After building fixtures (teams & matches).
      - After marking winners / resetting scores.

    This makes host rejoin cross-device: any host with the correct
    admin_passcode can GET this state and continue from where they left off.
    """
    # Ensure the session exists
    if not any(s.id == session_id for s in SESSIONS):
        raise HTTPException(status_code=404, detail="Session not found")

    SESSION_STATES[session_id] = state
    return state
