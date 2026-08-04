from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import uuid

app = FastAPI()

# ---------- CORS ----------

origins = [
    "https://courtsandrallies.netlify.app",
    # add other frontends here if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Models ----------

class SessionCreate(BaseModel):
    name: str
    admin_passcode: str

class Session(BaseModel):
    id: str
    name: str
    admin_passcode: str  # store passcode for host login later

SESSIONS: List[Session] = []

# ---------- Routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/sessions", response_model=Session)
def create_session(body: SessionCreate):
    """
    Create a new session with a name and admin passcode.
    Returns the session ID and name so the frontend can use it.
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

    Called by the frontend as:
    DELETE /sessions/<session_id>
    """
    global SESSIONS

    for i, s in enumerate(SESSIONS):
        if s.id == session_id:
            # remove the session from the in-memory list
            del SESSIONS[i]
            # 204 No Content — nothing else to send
            return Response(status_code=204)

    # If we get here, no session matched that ID
    raise HTTPException(status_code=404, detail="Session not found")
