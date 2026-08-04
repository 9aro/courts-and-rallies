from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import uuid

app = FastAPI()

class SessionCreate(BaseModel):
    name: str
    admin_passcode: str

class Session(BaseModel):
    id: str
    name: str

SESSIONS: List[Session] = []

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/sessions", response_model=Session)
def create_session(body: SessionCreate):
    session_id = str(uuid.uuid4())
    session = Session(id=session_id, name=body.name)
    SESSIONS.append(session)
    return session

@app.get("/sessions", response_model=List[Session])
def list_sessions():
    return SESSIONS
