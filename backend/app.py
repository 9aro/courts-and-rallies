from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uuid

app = FastAPI()

# ---------- CORS ----------

origins = [
    # Old Netlify frontend (still allowed if you keep using it)
    "https://courtsandrallies.netlify.app",

    # New GitHub Pages frontend
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

ADMIN_TOOLS_PASSCODE = "pickleball"  # tools/admin panel passcode

class SessionCreate(BaseModel):
    name: str
    admin_passcode: str

class Session(BaseModel):
    id: str
    name: str
    admin_passcode: str  # stored so host can log back in

SESSIONS: List[Session] = []

class HostLoginBody(BaseModel):
    admin_passcode: str

class AdminToolsLoginBody(BaseModel):
    tools_passcode: str

# ---------- Routes ----------

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
    """
    global SESSIONS

    for i, s in enumerate(SESSIONS):
        if s.id == session_id:
            del SESSIONS[i]
            return Response(status_code=204)

    raise HTTPException(status_code=404, detail="Session not found")

@app.post("/sessions/{session_id}/host-login", response_model=Session)
def host_login(session_id: str, body: HostLoginBody):
    """
    Verify the admin passcode for a session.

    Frontend calls (from Host existing session):
    POST /sessions/<session_id>/host-login
    body: { "admin_passcode": "..." }
    """
    for s in SESSIONS:
        if s.id == session_id:
            if s.admin_passcode == body.admin_passcode:
                return s
            raise HTTPException(status_code=401, detail="Wrong admin passcode")
    raise HTTPException(status_code=404, detail="Session not found")

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
