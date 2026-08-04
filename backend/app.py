from fastapi import FastAPI
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

SESSIONS: List[Session] = []

# ---------- Routes ----------

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
