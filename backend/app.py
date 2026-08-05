import os
import uuid
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

app = FastAPI()

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

ADMIN_TOOLS_PASSCODE = "pickleball"
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


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
    winner: Optional[str] = None


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


@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        conn.execute(text("""
            create table if not exists sessions (
              id text primary key,
              name text not null,
              admin_passcode text not null
            )
        """))
        conn.execute(text("""
            create table if not exists session_states (
              session_id text primary key references sessions(id) on delete cascade,
              state jsonb not null
            )
        """))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions", response_model=Session)
def create_session(body: SessionCreate):
    session_id = str(uuid.uuid4())
    try:
        with engine.begin() as conn:
            conn.execute(
                text("insert into sessions (id, name, admin_passcode) values (:id, :name, :admin_passcode)"),
                {"id": session_id, "name": body.name, "admin_passcode": body.admin_passcode},
            )
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error creating session: {str(e)}")

    return Session(id=session_id, name=body.name, admin_passcode=body.admin_passcode)


@app.get("/sessions", response_model=List[Session])
def list_sessions():
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("select id, name, admin_passcode from sessions order by name asc")).mappings().all()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error listing sessions: {str(e)}")

    return [Session(**row) for row in rows]


@app.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    try:
        with engine.begin() as conn:
            result = conn.execute(text("delete from sessions where id = :id"), {"id": session_id})
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Session not found")
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error deleting session: {str(e)}")

    return Response(status_code=204)


@app.post("/sessions/{session_id}/host-login", response_model=Session)
def host_login(session_id: str, body: HostLoginBody):
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("select id, name, admin_passcode from sessions where id = :id"),
                {"id": session_id},
            ).mappings().first()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error on host login: {str(e)}")

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    if row["admin_passcode"] != body.admin_passcode:
        raise HTTPException(status_code=401, detail="Wrong admin passcode")

    return Session(**row)


@app.post("/admin/tools-login")
def admin_tools_login(body: AdminToolsLoginBody):
    if body.tools_passcode == ADMIN_TOOLS_PASSCODE:
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Wrong admin tools passcode")


@app.get("/sessions/{session_id}/state", response_model=SessionState)
def get_session_state(session_id: str):
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text("select state from session_states where session_id = :session_id"),
                {"session_id": session_id},
            ).mappings().first()
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error loading session state: {str(e)}")

    if not row:
        raise HTTPException(status_code=404, detail="Session state not found")

    return row["state"]


@app.put("/sessions/{session_id}/state", response_model=SessionState)
def put_session_state(session_id: str, state: SessionState):
    try:
        with engine.begin() as conn:
            exists = conn.execute(
                text("select 1 from sessions where id = :id"),
                {"id": session_id},
            ).first()
            if not exists:
                raise HTTPException(status_code=404, detail="Session not found")

            conn.execute(
                text("""
                    insert into session_states (session_id, state)
                    values (:session_id, cast(:state as jsonb))
                    on conflict (session_id)
                    do update set state = excluded.state
                """),
                {"session_id": session_id, "state": state.model_dump_json()},
            )
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error saving session state: {str(e)}")

    return state
