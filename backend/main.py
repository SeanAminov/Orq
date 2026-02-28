"""
Orq  --  FastAPI backend
Slack-like room architecture with AI intent routing.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager

import bcrypt
import requests
from fastapi import FastAPI, Depends, HTTPException, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError
from pydantic import BaseModel
from loguru import logger
from sqlalchemy.orm import Session

from database import SessionLocal, engine, Base
from models import User, UserCredential, Message, Activity, Room, RoomMember, AgentRun, Memory, Workflow
from config import (
    SECRET_KEY, OPENAI_MODEL,
    get_openai_client,
    get_composio_client, get_composio_tools, execute_composio_tool,
    get_snowflake_connection,
    SKYFIRE_API_KEY, SKYFIRE_BASE_URL,
    COMPOSIO_API_KEY,
)
from crew import run_crew
from candidate_crew import run_candidate_research
from digest_crew import run_commit_digest
from github_tools import (
    fetch_user_repos, fetch_repo_details, fetch_repo_languages,
    fetch_repo_commits, fetch_commit_details,
)

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Orq backend started")
    yield
    logger.info("Orq backend stopped")

app = FastAPI(title="Orq", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

ALGORITHM = "HS256"
TOKEN_HOURS = 24

def _create_token(user_id: str) -> str:
    return jwt.encode(
        {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)},
        SECRET_KEY, algorithm=ALGORITHM,
    )

def _set_cookie(resp: Response, token: str):
    resp.set_cookie("token", token, httponly=True, samesite="lax", max_age=TOKEN_HOURS * 3600)

def get_current_user(req: Request, db: Session = Depends(get_db)) -> User:
    token = req.cookies.get("token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.query(User).filter(User.id == payload["sub"]).first()
        if not user:
            raise HTTPException(401, "User not found")
        return user
    except JWTError:
        raise HTTPException(401, "Invalid token")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoginBody(BaseModel):
    email: str
    password: str

class SignupBody(BaseModel):
    email: str
    password: str
    name: str

class ChatBody(BaseModel):
    message: str
    mode: str = "chat"

class CreateRoomBody(BaseModel):
    name: str
    icon: str = "\U0001f4ac"
    description: str = ""
    github_repo: str | None = None
    member_ids: list[str] | None = None

class RoomMessageBody(BaseModel):
    message: str

class RoomRunBody(BaseModel):
    message: str
    intent_hint: str | None = None

class ComposioConnectBody(BaseModel):
    app_name: str

class SummaryBody(BaseModel):
    email: str

class CandidateResearchBody(BaseModel):
    github_username: str
    target_role: str
    candidate_name: str = ""
    company_context: str = ""
    resume_text: str = ""
    generate_outreach: bool = False

class CommitDigestBody(BaseModel):
    repo: str
    author: str | None = None
    path_filter: str | None = None
    since_days: int = 7
    max_commits: int = 30
    email_to: str | None = None
    create_doc: bool = False

class WorkflowStepBody(BaseModel):
    type: str
    prompt: str
    tool: str | None = None

class WorkflowCreateBody(BaseModel):
    name: str
    trigger: str
    description: str = ""
    steps: list[WorkflowStepBody]
    room_id: str | None = None

# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.post("/api/auth/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.credentials:
        raise HTTPException(401, "Invalid credentials")
    if not bcrypt.checkpw(body.password.encode(), user.credentials.password_hash.encode()):
        raise HTTPException(401, "Invalid credentials")
    user.last_seen_at = datetime.now(timezone.utc)
    db.commit()
    resp = Response(content='{"ok":true}', media_type="application/json")
    _set_cookie(resp, _create_token(user.id))
    return resp

@app.post("/api/auth/signup")
def signup(body: SignupBody, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    db.add(User(id=uid, email=body.email, name=body.name, created_at=now, last_seen_at=now))
    db.add(UserCredential(user_id=uid, password_hash=pw_hash, created_at=now))
    db.commit()
    resp = Response(content='{"ok":true}', media_type="application/json")
    _set_cookie(resp, _create_token(uid))
    return resp

@app.post("/api/auth/logout")
def logout():
    resp = Response(content='{"ok":true}', media_type="application/json")
    resp.delete_cookie("token")
    return resp

@app.get("/api/auth/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "role": user.role}

@app.get("/api/users")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List all users except the current user (for member picker)."""
    users = db.query(User).filter(User.id != user.id).all()
    return [{"id": u.id, "name": u.name, "email": u.email} for u in users]

# ===========================================================================
#  ROOM ENDPOINTS (Slack-like architecture)
# ===========================================================================

@app.get("/api/rooms")
def list_rooms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List rooms the current user belongs to."""
    memberships = (
        db.query(RoomMember)
        .filter(RoomMember.user_id == user.id)
        .all()
    )
    room_ids = [m.room_id for m in memberships]
    if not room_ids:
        return []
    rooms = db.query(Room).filter(Room.id.in_(room_ids)).order_by(Room.created_at.asc()).all()
    return [
        {
            "id": r.id, "name": r.name, "icon": r.icon,
            "description": r.description, "github_repo": r.github_repo,
            "skyfire_budget": r.skyfire_budget, "created_at": str(r.created_at),
        }
        for r in rooms
    ]

@app.post("/api/rooms")
def create_room(body: CreateRoomBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new room with specified members (or just the creator)."""
    room_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(Room(
        id=room_id, name=body.name, icon=body.icon,
        description=body.description, github_repo=body.github_repo,
        created_by=user.id, created_at=now,
    ))
    # determine members: explicit list or just the creator
    if body.member_ids:
        member_set = set(body.member_ids)
        member_set.add(user.id)  # always include creator
    else:
        member_set = {user.id}
    for uid in member_set:
        db.add(RoomMember(id=str(uuid.uuid4()), room_id=room_id, user_id=uid, joined_at=now))
    db.commit()
    return {"id": room_id, "name": body.name, "icon": body.icon}

@app.get("/api/rooms/{room_id}/messages")
def get_room_messages(room_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get messages for a room."""
    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, RoomMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this room")
    msgs = (
        db.query(Message)
        .filter(Message.room_id == room_id)
        .order_by(Message.created_at.asc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": m.id, "sender_id": m.sender_id, "sender_name": m.sender_name,
            "role": m.role, "content": m.content, "run_id": m.run_id,
            "created_at": str(m.created_at),
        }
        for m in msgs
    ]

@app.post("/api/rooms/{room_id}/messages")
def send_room_message(room_id: str, body: RoomMessageBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Send a plain message to a room (no AI processing)."""
    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, RoomMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this room")
    now = datetime.now(timezone.utc)
    msg_id = str(uuid.uuid4())
    db.add(Message(
        id=msg_id, room_id=room_id, user_id=user.id,
        sender_id=user.id, sender_name=user.name,
        role="user", content=body.message, created_at=now,
    ))
    db.commit()
    return {"id": msg_id, "content": body.message, "sender_name": user.name}

@app.post("/api/rooms/{room_id}/run")
def run_agent_in_room(room_id: str, body: RoomRunBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Unified agent endpoint: classify intent and route to the right handler.
    This is the core of the @orq experience.
    """
    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, RoomMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this room")

    now = datetime.now(timezone.utc)
    message = body.message.strip()

    # save user message to room
    db.add(Message(
        id=str(uuid.uuid4()), room_id=room_id, user_id=user.id,
        sender_id=user.id, sender_name=user.name,
        role="user", content=message, created_at=now,
    ))
    db.commit()

    # extract memories from user message (async-safe, non-blocking)
    _extract_memories(db, user, message, room_id)

    # check for custom workflow triggers before intent classification
    workflow_result = _check_workflow_trigger(message, user, db, room_id)
    if workflow_result is not None:
        # workflow matched — save result and return
        run_id = str(uuid.uuid4())
        tokens = workflow_result.get("tokens", 0)
        cost = workflow_result.get("cost", 0.0)
        reply = workflow_result.get("reply", "Workflow completed.")
        db.add(AgentRun(
            id=run_id, room_id=room_id, user_id=user.id,
            user_name=user.name, intent="WORKFLOW", status="completed",
            input_text=message[:200], summary=reply[:500],
            tokens_used=str(tokens), cost_usd=f"{cost:.6f}",
            created_at=now, completed_at=datetime.now(timezone.utc),
        ))
        room = db.query(Room).filter(Room.id == room_id).first()
        if room and cost > 0:
            prev = float(room.skyfire_budget or "0")
            room.skyfire_budget = f"{prev + cost:.6f}"
        db.add(Message(
            id=str(uuid.uuid4()), room_id=room_id, user_id=user.id,
            sender_id="assistant", sender_name="Orq",
            role="assistant", content=reply, run_id=run_id,
            created_at=datetime.now(timezone.utc),
        ))
        db.add(Activity(
            id=str(uuid.uuid4()), user_id=user.id, user_name=user.name,
            summary=f"[Workflow] {message[:80]}",
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()
        return {"reply": reply, "intent": "workflow", "run_id": run_id, "tokens": tokens, "cost_usd": f"{cost:.6f}"}

    # classify intent -- use hint if provided and valid
    valid_intents = {"CREW", "ACTION", "DATA", "PAY", "CHAT", "RESEARCH", "CLEAN"}
    hint_map = {"SUMMARY": "DATA", "RESEARCH": "RESEARCH", "CLEAN": "CLEAN"}

    if body.intent_hint:
        raw_hint = body.intent_hint.upper()
        mapped = hint_map.get(raw_hint, raw_hint)
        if mapped in valid_intents:
            intent = mapped
            logger.info(f"[room:{room_id}] intent_hint={intent} from user={user.name}")
        else:
            client = get_openai_client()
            if not client:
                return {"reply": "OpenAI not configured.", "intent": "error", "run_id": None}
            intent = _classify_intent(client, message)
            logger.info(f"[room:{room_id}] intent={intent} (hint invalid) from user={user.name}")
    else:
        client = get_openai_client()
        if not client:
            return {"reply": "OpenAI not configured.", "intent": "error", "run_id": None}
        intent = _classify_intent(client, message)
        logger.info(f"[room:{room_id}] intent={intent} from user={user.name}")

    # create agent run record
    run_id = str(uuid.uuid4())
    db.add(AgentRun(
        id=run_id, room_id=room_id, user_id=user.id,
        user_name=user.name, intent=intent, status="running",
        input_text=message[:200], created_at=now,
    ))
    db.commit()

    # route to handler
    handlers = {
        "CHAT":     _do_chat,
        "CREW":     _do_crew,
        "ACTION":   _do_composio_action,
        "DATA":     _do_snowflake_query,
        "PAY":      _do_skyfire_payment,
        "RESEARCH": _do_skyfire_research,
        "CLEAN":    _do_skyfire_clean,
    }
    handler = handlers.get(intent, _do_chat)

    # @summary strips the trigger, so re-inject "summarize:" context
    handler_message = message
    if body.intent_hint and body.intent_hint.upper() == "SUMMARY":
        handler_message = f"summarize the following: {message}"

    tokens = 0
    cost = 0.0
    try:
        result = handler(handler_message, user, db, room_id)
        # handlers return {"reply": ..., "tokens": ..., "cost": ...}
        reply = result.get("reply", str(result)) if isinstance(result, dict) else str(result)
        tokens = result.get("tokens", 0) if isinstance(result, dict) else 0
        cost = result.get("cost", 0.0) if isinstance(result, dict) else 0.0
        status = "completed"
    except Exception as e:
        logger.error(f"[room:{room_id}] {intent} error: {e}")
        reply = f"Error: {e}"
        status = "failed"

    # update agent run with cost
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.status = status
        run.summary = reply[:500] if reply else ""
        run.tokens_used = str(tokens)
        run.cost_usd = f"{cost:.6f}"
        run.completed_at = datetime.now(timezone.utc)

    # accumulate cost on room
    room = db.query(Room).filter(Room.id == room_id).first()
    if room and cost > 0:
        prev = float(room.skyfire_budget or "0")
        room.skyfire_budget = f"{prev + cost:.6f}"

    # save assistant reply to room
    db.add(Message(
        id=str(uuid.uuid4()), room_id=room_id, user_id=user.id,
        sender_id="assistant", sender_name="Orq",
        role="assistant", content=reply, run_id=run_id,
        created_at=datetime.now(timezone.utc),
    ))

    # log to team activity
    intent_labels = {"CREW": "Crew", "ACTION": "Action", "DATA": "Data", "PAY": "Skyfire", "CHAT": "Chat"}
    short_msg = message[:80] + ("..." if len(message) > 80 else "")
    db.add(Activity(
        id=str(uuid.uuid4()), user_id=user.id,
        user_name=user.name,
        summary=f"[{intent_labels.get(intent, intent)}] {short_msg}",
        created_at=datetime.now(timezone.utc),
    ))

    db.commit()
    return {"reply": reply, "intent": intent.lower(), "run_id": run_id, "tokens": tokens, "cost_usd": f"{cost:.6f}"}

@app.get("/api/rooms/{room_id}/runs")
def get_room_runs(room_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get agent runs for a room (activity panel)."""
    member = db.query(RoomMember).filter(
        RoomMember.room_id == room_id, RoomMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(403, "Not a member of this room")
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.room_id == room_id)
        .order_by(AgentRun.created_at.desc())
        .limit(30)
        .all()
    )
    return [
        {
            "id": r.id, "intent": r.intent, "status": r.status,
            "user_name": r.user_name, "input_text": r.input_text,
            "summary": r.summary[:200] if r.summary else "",
            "tokens_used": r.tokens_used or "0",
            "cost_usd": r.cost_usd or "0.00",
            "created_at": str(r.created_at),
            "completed_at": str(r.completed_at) if r.completed_at else None,
        }
        for r in runs
    ]

# ===========================================================================
#  INTENT CLASSIFIER
# ===========================================================================

def _classify_intent(client, message: str) -> str:
    """Use OpenAI to detect what the user wants to do."""
    # Fast-path: if the message mentions GitHub, repos, commits, candidates,
    # or code contributions, route directly to CREW (never DATA/Snowflake).
    msg_lower = message.lower()
    _crew_fast_keywords = [
        "github", "repo", "repos", "repository", "commit", "commits",
        "pushed", "code change", "pull request", "code pushed",
        "candidate", "developer profile", "evaluate developer",
        "their profile", "contribution", "who coded", "who worked on",
        "what did", "what was added", "what was changed", "last code",
        "latest code", "recent code", "code by", "worked on frontend",
        "worked on backend", "added to frontend", "added to backend",
        "git log", "commit history", "check their", "look at their",
        "fit for", "good fit", "qualification", "interview question",
        "hire", "hiring", "research this", "tell me about this person",
    ]
    if any(kw in msg_lower for kw in _crew_fast_keywords):
        return "CREW"

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "Classify the user's intent into exactly one label. Respond with ONLY the label.\n\n"
                "CREW - complex multi-step task, research, analysis, multi-agent work, "
                "candidate research, commit digest, anything needing multiple agents, "
                "ANY question about GitHub, repositories, commits, code contributions, "
                "developer profiles, or code changes (NEVER classify GitHub/code as DATA)\n"
                "ACTION - send email, draft email, check emails, create Google Doc, "
                "list Google Drive files (Google/Composio integrations)\n"
                "DATA - sentiment analysis, translation, text summarization, "
                "Snowflake SQL queries on database tables (NOT code/GitHub questions)\n"
                "PAY - Skyfire payments, balance check, payment tokens, "
                "pay-per-query AI, anything about Skyfire\n"
                "CHAT - general conversation, questions, help, explanations, brainstorming\n\n"
                "IMPORTANT: Questions about code, GitHub, repositories, commits, or developers "
                "are ALWAYS CREW, never DATA.\n\n"
                "Return ONLY one of: CREW, ACTION, DATA, PAY, CHAT"
            )},
            {"role": "user", "content": message},
        ],
    )
    label = resp.choices[0].message.content.strip().upper()
    for valid in ["CREW", "ACTION", "DATA", "PAY", "CHAT"]:
        if valid in label:
            return valid
    return "CHAT"

# ===========================================================================
#  COST TRACKING HELPERS
# ===========================================================================

# GPT-4o-mini pricing (per 1K tokens)
_COST_PER_1K_INPUT = 0.00015
_COST_PER_1K_OUTPUT = 0.0006

def _calc_cost(usage) -> dict:
    """Extract token count and estimated cost from an OpenAI usage object."""
    if not usage:
        return {"tokens": 0, "cost": 0.0}
    inp = getattr(usage, "prompt_tokens", 0) or 0
    out = getattr(usage, "completion_tokens", 0) or 0
    total = inp + out
    cost = (inp / 1000 * _COST_PER_1K_INPUT) + (out / 1000 * _COST_PER_1K_OUTPUT)
    return {"tokens": total, "cost": round(cost, 6)}

def _cost_result(reply: str, tokens: int = 0, cost: float = 0.0) -> dict:
    """Wrap a handler reply with cost metadata."""
    return {"reply": reply, "tokens": tokens, "cost": cost}

# ===========================================================================
#  SHARED MEMORY -- cross-agent context
# ===========================================================================

def _get_shared_context(db: Session, room_id: str = None, limit: int = 15) -> str:
    """
    Build shared context from recent AgentRun records so all handlers
    are aware of what other agents have done. This is the 'brain' of the
    system -- every handler gets this context injected.
    """
    if not room_id:
        return ""
    runs = (
        db.query(AgentRun)
        .filter(AgentRun.room_id == room_id, AgentRun.status == "completed")
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
        .all()
    )[::-1]
    if not runs:
        return ""
    lines = []
    for r in runs:
        ts = r.created_at.strftime("%m/%d %H:%M") if r.created_at else ""
        summary = (r.summary or "")[:300]
        if summary:
            lines.append(f"[{ts}] @{r.intent.lower()} by {r.user_name}: {r.input_text[:100]}\n  Result: {summary}")
    if not lines:
        return ""
    return (
        "\n\nSHARED MEMORY -- Recent agent activity in this room:\n"
        + "\n".join(lines[-10:])
        + "\n\nUse this context to provide continuity. Reference prior results when relevant."
    )


# ===========================================================================
#  LEARNING MEMORY -- extract and inject user memories
# ===========================================================================

def _extract_memories(db: Session, user: User, message: str, room_id: str = None):
    """
    After each user message, use LLM to detect teachable facts and upsert
    them into the Memory table. Cheap call (~100 tokens).
    """
    client = get_openai_client()
    if not client:
        return
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": (
                    "You are a memory extraction agent. Analyze the user's message and extract "
                    "any teachable facts worth remembering for future use.\n\n"
                    "Extract facts like:\n"
                    "- Contact info: \"Yug's email is yugmore20@gmail.com\" -> {category: 'contact', subject: 'Yug', key: 'email', value: 'yugmore20@gmail.com'}\n"
                    "- Preferences: \"I prefer dark mode\" -> {category: 'preference', subject: 'user', key: 'theme', value: 'dark mode'}\n"
                    "- Project facts: \"Our deadline is March 15\" -> {category: 'project', subject: 'project', key: 'deadline', value: 'March 15'}\n"
                    "- GitHub usernames: \"Sean's github is SeanAminov\" -> {category: 'contact', subject: 'Sean', key: 'github', value: 'SeanAminov'}\n"
                    "- Roles/titles: \"Yug is the frontend lead\" -> {category: 'fact', subject: 'Yug', key: 'role', value: 'frontend lead'}\n\n"
                    "Return a JSON array of objects with {category, subject, key, value}.\n"
                    "Return [] if nothing worth remembering.\n"
                    "Only extract EXPLICIT facts the user states, not inferences.\n"
                    "Return ONLY the JSON array, no other text."
                )},
                {"role": "user", "content": message},
            ],
        )
        text = resp.choices[0].message.content.strip()
        memories = _safe_json_array(text)
        if not memories:
            return

        now = datetime.now(timezone.utc)
        for mem in memories:
            cat = mem.get("category", "fact")
            subj = mem.get("subject", "")
            key = mem.get("key", "")
            val = mem.get("value", "")
            if not subj or not key or not val:
                continue
            # Upsert: update if same user+subject+key exists
            existing = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.subject == subj,
                Memory.key == key,
            ).first()
            if existing:
                existing.value = val
                existing.source_msg = message[:300]
                existing.updated_at = now
            else:
                db.add(Memory(
                    id=str(uuid.uuid4()),
                    user_id=user.id,
                    room_id=room_id,
                    category=cat,
                    subject=subj,
                    key=key,
                    value=val,
                    source_msg=message[:300],
                    created_at=now,
                    updated_at=now,
                ))
        db.commit()
        logger.info(f"[memory] extracted {len(memories)} memories from {user.name}")
    except Exception as e:
        db.rollback()
        logger.error(f"[memory] extraction error: {e}")


def _get_user_memories(db: Session, user_id: str, room_id: str = None) -> str:
    """
    Query Memory table for user's personal + room-scoped memories.
    Returns formatted string block for injection into system prompts.
    """
    query = db.query(Memory).filter(Memory.user_id == user_id)
    if room_id:
        query = query.filter((Memory.room_id == room_id) | (Memory.room_id.is_(None)))
    memories = query.order_by(Memory.updated_at.desc()).limit(50).all()
    if not memories:
        return ""
    lines = []
    for m in memories:
        lines.append(f"- {m.subject}'s {m.key}: {m.value}")
    return (
        "\n\nUSER MEMORY -- Facts you've learned about this user and their contacts:\n"
        + "\n".join(lines)
        + "\n\nUse this memory to fill in details automatically (e.g., email addresses, "
        "GitHub usernames, preferences). If critical info is missing for a task, ask the user."
    )


def _safe_json_array(text: str) -> list:
    """Parse JSON array from LLM output, handling markdown fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        result = json.loads(text)
        return result if isinstance(result, list) else []
    except json.JSONDecodeError:
        return []


# ===========================================================================
#  CUSTOM WORKFLOWS -- trigger detection and sequential step execution
# ===========================================================================

def _check_workflow_trigger(message: str, user: User, db: Session, room_id: str = None) -> dict | None:
    """
    Check if the message starts with a custom workflow trigger.
    Returns workflow result dict or None if no trigger matched.
    """
    msg_lower = message.strip().lower()
    # Workflows are triggered by @TriggerName
    if not msg_lower.startswith("@"):
        return None
    # Extract the trigger word (first word after @)
    parts = message.strip().split(None, 1)
    trigger_word = parts[0][1:]  # remove the @
    if not trigger_word:
        return None
    # Skip built-in triggers
    builtins = {"orq", "crew", "action", "data", "pay", "summary"}
    if trigger_word.lower() in builtins:
        return None
    # Look up in Workflow table (own workflows + room-shared workflows)
    wf_filter = Workflow.owner_id == user.id
    if room_id:
        wf_filter = wf_filter | (Workflow.room_id == room_id)
    workflow = db.query(Workflow).filter(
        Workflow.trigger.ilike(trigger_word),
        Workflow.is_active == "true",
        wf_filter,
    ).first()
    if not workflow:
        return None
    extra_input = parts[1] if len(parts) > 1 else ""
    logger.info(f"[workflow] triggered '{workflow.name}' by {user.name}")
    return _run_workflow(workflow, extra_input, user, db, room_id)


def _run_workflow(workflow: "Workflow", extra_input: str, user: User, db: Session, room_id: str = None) -> dict:
    """
    Execute a workflow's steps sequentially. Each step calls an existing
    handler. {{prev_result}} is replaced with the previous step's output.
    """
    try:
        steps = json.loads(workflow.steps)
    except json.JSONDecodeError:
        return _cost_result(f"Workflow '{workflow.name}' has invalid steps configuration.")

    total_tokens = 0
    total_cost = 0.0
    prev_result = extra_input or ""
    all_replies = []

    for i, step in enumerate(steps):
        step_type = step.get("type", "chat").lower()
        prompt = step.get("prompt", "")
        # Replace {{prev_result}} placeholder
        prompt = prompt.replace("{{prev_result}}", prev_result)
        if extra_input and i == 0:
            prompt = f"{prompt}\n\nAdditional context: {extra_input}"

        logger.info(f"[workflow] step {i+1}/{len(steps)}: {step_type} — {prompt[:80]}")

        handlers = {
            "chat": _do_chat,
            "action": _do_composio_action,
            "crew": _do_crew,
            "data": _do_snowflake_query,
            "pay": _do_skyfire_payment,
            "research": _do_skyfire_research,
            "clean": _do_skyfire_clean,
        }
        handler = handlers.get(step_type, _do_chat)
        try:
            result = handler(prompt, user, db, room_id)
            reply = result.get("reply", str(result)) if isinstance(result, dict) else str(result)
            total_tokens += result.get("tokens", 0) if isinstance(result, dict) else 0
            total_cost += result.get("cost", 0.0) if isinstance(result, dict) else 0.0
        except Exception as e:
            reply = f"Step {i+1} failed: {e}"
            logger.error(f"[workflow] step {i+1} error: {e}")

        prev_result = reply
        all_replies.append(f"**Step {i+1}: {step_type.title()}**\n{reply}")

    combined = f"**Workflow: {workflow.name}** ({len(steps)} steps)\n\n" + "\n\n".join(all_replies)
    return _cost_result(combined, total_tokens, total_cost)


# ===========================================================================
#  CODE CONTRIBUTION QUERY -- fast GitHub API path for room-linked repos
# ===========================================================================

def _do_contribution_query(message: str, user: User, db: Session, room_id: str) -> dict | None:
    """
    Detect contribution-related questions and answer them using the
    room's linked github_repo. Returns None if this isn't a contribution
    query or the room has no linked repo.

    Handles: "what did X add", "X's commits", "who worked on frontend",
    "last changes to backend", "show me recent code changes", etc.
    """
    msg_lower = message.lower()
    contribution_keywords = [
        "what did", "who coded", "who worked", "who added", "who pushed",
        "who committed", "last commit", "recent commit", "code change",
        "what was added", "what was changed", "contribution", "wrote code",
        "added to frontend", "added to backend", "changed in frontend",
        "changed in backend", "worked on frontend", "worked on backend",
        "pushed to", "latest changes", "recent changes", "what code",
        "show commits", "git log", "commit history", "what changed",
        "last code pushed", "code pushed by", "last push", "last thing",
        "tell me the last", "tell me what", "show me what", "what has",
        "what have", "changes by", "changes from", "pushed by",
        "committed by", "work done by", "last update", "recent update",
        "code from", "built by", "developed by",
    ]
    if not any(kw in msg_lower for kw in contribution_keywords):
        return None

    if not room_id:
        return None

    room = db.query(Room).filter(Room.id == room_id).first()
    if not room or not room.github_repo:
        return None

    client = get_openai_client()
    if not client:
        return _cost_result("OpenAI not configured.")

    total_tokens = 0
    total_cost = 0.0

    # Parse the repo (owner/repo format)
    repo_parts = room.github_repo.strip().split("/")
    if len(repo_parts) < 2:
        return None
    owner = repo_parts[-2]
    repo = repo_parts[-1]

    # Use LLM to extract author, path, and timeframe from the message
    extract = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "Extract from the user's message about code contributions.\n"
                "Return JSON: {\"author\": \"...\", \"path_filter\": \"...\", \"since_days\": 7}\n"
                "- author: the GitHub username or name of the person they're asking about. null if asking about all contributors.\n"
                "- path_filter: the directory/path filter like 'frontend/' or 'backend/' or 'src/'. null if no specific path.\n"
                "- since_days: how many days back to look. Default 7.\n"
                "Use null for missing fields."
            )},
            {"role": "user", "content": message},
        ],
    )
    ci = _calc_cost(extract.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    params = _safe_json(extract.choices[0].message.content)

    author = params.get("author")
    path_filter = params.get("path_filter")
    since_days = params.get("since_days", 7) or 7

    # Fetch commits from GitHub API
    commits = fetch_repo_commits(
        owner, repo,
        author=author,
        since_days=since_days,
        max_commits=20,
        path_filter=path_filter,
    )

    if not commits or (isinstance(commits, list) and len(commits) == 1 and isinstance(commits[0], dict) and "error" in commits[0]):
        error_msg = commits[0].get("error", "Unknown error") if commits else "No data"
        return _cost_result(
            f"Could not fetch commits from **{owner}/{repo}**: {error_msg}\n\n"
            f"_Searched: author={author or 'all'}, path={path_filter or 'all'}, last {since_days} days_",
            total_tokens, total_cost,
        )

    # Get detailed info for up to 5 most recent commits
    detailed_commits = []
    for c in commits[:5]:
        sha = c.get("sha", "")
        if sha:
            detail = fetch_commit_details(owner, repo, sha)
            if isinstance(detail, dict) and "error" not in detail:
                detailed_commits.append(detail)
            else:
                detailed_commits.append(c)
        else:
            detailed_commits.append(c)

    # Build context and summarize with LLM
    commit_data = json.dumps(detailed_commits, indent=2, default=str)[:6000]
    all_commits_summary = json.dumps(commits, indent=2, default=str)[:3000]

    # Get room member info for name resolution
    members = (
        db.query(User)
        .join(RoomMember, RoomMember.user_id == User.id)
        .filter(RoomMember.room_id == room_id)
        .all()
    )
    member_names = ", ".join(f"{m.name} ({m.email})" for m in members)

    summary_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are Orq, a code contribution analyst. Summarize the commit data "
                "into a clear, useful response. Focus on WHAT was built/changed, "
                "which files were affected, and the impact.\n\n"
                "Format with markdown: use headers, bullet points, and code blocks for paths.\n"
                "Group changes by feature or area (frontend, backend, config, etc.).\n"
                "Be specific about file names and what the code does.\n"
                "Do NOT use horizontal rules (---) in your response.\n"
                f"Room members: {member_names}\n"
                f"Repository: {owner}/{repo}"
            )},
            {"role": "user", "content": (
                f"User asked: {message}\n\n"
                f"Detailed commits (last {len(detailed_commits)}):\n{commit_data}\n\n"
                f"All commits summary ({len(commits)} total):\n{all_commits_summary}"
            )},
        ],
    )
    ci2 = _calc_cost(summary_resp.usage)
    total_tokens += ci2["tokens"]
    total_cost += ci2["cost"]

    reply = summary_resp.choices[0].message.content
    # Add metadata footer
    reply += (
        f"\n\n"
        f"_Source: [{owner}/{repo}](https://github.com/{owner}/{repo}) · "
        f"{len(commits)} commits · "
        f"Author: {author or 'all'} · "
        f"Path: {path_filter or 'all'} · "
        f"Last {since_days} days_"
    )
    return _cost_result(reply, total_tokens, total_cost)


# ===========================================================================
#  GITHUB DIRECT QUERY -- fast path for GitHub questions without full crew
# ===========================================================================

def _do_github_direct_query(message: str, user: User, db: Session, room_id: str = None) -> dict | None:
    """
    Handle direct GitHub questions by fetching real data from GitHub API
    and summarizing with OpenAI. Returns None if we can't extract a
    GitHub username/repo from the message.
    """
    client = get_openai_client()
    if not client:
        return None

    total_tokens = 0
    total_cost = 0.0

    # Use LLM to extract GitHub info from the message
    extract = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "Extract GitHub information from the user's message.\n"
                "Return JSON: {\"username\": \"...\", \"repo\": \"...\", \"query_type\": \"...\", \"author_filter\": \"...\"}\n"
                "- username: GitHub username mentioned (e.g., 'SeanAminov', 'Yug-More')\n"
                "- repo: specific repo name if mentioned (e.g., 'Orq'). null if not mentioned.\n"
                "- query_type: one of 'repos' (list user's repos), 'commits' (show commits), "
                "'repo_detail' (details about a specific repo), 'profile' (general GitHub profile overview)\n"
                "- author_filter: if asking about commits by a specific person, their name/username. null otherwise.\n"
                "Return empty strings if you cannot identify a GitHub username."
            )},
            {"role": "user", "content": message},
        ],
    )
    ci = _calc_cost(extract.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    params = _safe_json(extract.choices[0].message.content)

    username = params.get("username", "").strip()
    if not username:
        return None  # Can't identify a GitHub user, fall through to general crew

    repo_name = params.get("repo", "")
    query_type = params.get("query_type", "profile")
    author_filter = params.get("author_filter", "")

    # Fetch real GitHub data
    github_data = {}
    try:
        repos = fetch_user_repos(username, max_repos=8)
        github_data["repos"] = repos

        # If specific repo mentioned, get details
        if repo_name:
            detail = fetch_repo_details(username, repo_name)
            langs = fetch_repo_languages(username, repo_name)
            commits = fetch_repo_commits(
                username, repo_name,
                author=author_filter or None,
                since_days=30,
                max_commits=15,
            )
            github_data["repo_detail"] = detail
            github_data["repo_languages"] = langs
            github_data["repo_commits"] = commits
        else:
            # Get details on top 3 repos
            enriched = []
            for r in repos[:3]:
                if isinstance(r, dict) and "error" not in r:
                    name = r.get("name", "")
                    if name:
                        detail = fetch_repo_details(username, name)
                        langs = fetch_repo_languages(username, name)
                        commits = fetch_repo_commits(username, name, max_commits=5, since_days=30)
                        enriched.append({
                            "repo": name,
                            "detail": detail,
                            "languages": langs,
                            "recent_commits": commits[:5],
                        })
            github_data["enriched_repos"] = enriched

        # Check for errors
        if isinstance(repos, list) and len(repos) == 1 and isinstance(repos[0], dict) and "error" in repos[0]:
            return _cost_result(
                f"Could not fetch GitHub data for **{username}**: {repos[0].get('error', 'Unknown error')}\n\n"
                f"Make sure the username is correct and the profile is public.",
                total_tokens, total_cost,
            )

    except Exception as e:
        logger.error(f"[github_direct] fetch error: {e}")
        return _cost_result(f"Error fetching GitHub data for {username}: {e}", total_tokens, total_cost)

    # Summarize with LLM
    gh_json = json.dumps(github_data, indent=2, default=str)[:8000]
    summary_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are Orq, a GitHub data analyst. Summarize the fetched GitHub data "
                "into a clear, useful response that directly answers the user's question.\n\n"
                "Format with markdown: use headers, bullet points, bold for emphasis.\n"
                "Include specific data: repo names, languages, stars, commit messages, dates.\n"
                "Be factual -- only report what the data shows. If data is empty, say so clearly.\n"
                "Add a link to the GitHub profile at the end.\n"
                "Do NOT use horizontal rules (---) in your response."
            )},
            {"role": "user", "content": (
                f"User asked: {message}\n\n"
                f"GitHub data for {username}:\n{gh_json}"
            )},
        ],
    )
    ci2 = _calc_cost(summary_resp.usage)
    total_tokens += ci2["tokens"]
    total_cost += ci2["cost"]

    reply = summary_resp.choices[0].message.content
    reply += f"\n\n_Source: [github.com/{username}](https://github.com/{username})_"
    return _cost_result(reply, total_tokens, total_cost)


# ===========================================================================
#  MODE HANDLERS
# ===========================================================================

# --- 1. Chat (OpenAI) -----------------------------------------------------

def _do_chat(message: str, user: User, db: Session, room_id: str = None) -> dict:
    # Fast path: code contribution queries use GitHub API directly
    contrib_result = _do_contribution_query(message, user, db, room_id)
    if contrib_result is not None:
        return contrib_result

    # Fast path: direct GitHub queries (when user mentions a GitHub username/repo)
    msg_lower = message.lower()
    _gh_chat_keywords = [
        "github", "repo ", "repos", "repository", "commit", "commits",
        "pushed", "code by", "last code", "latest project",
        "github.com/",
    ]
    if any(kw in msg_lower for kw in _gh_chat_keywords):
        gh_result = _do_github_direct_query(message, user, db, room_id)
        if gh_result is not None:
            return gh_result

    client = get_openai_client()
    if not client:
        return _cost_result("OpenAI is not configured. Set OPENAI_API_KEY in .env.")
    if room_id:
        history = (
            db.query(Message)
            .filter(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(20)
            .all()
        )[::-1]
    else:
        history = (
            db.query(Message)
            .filter(Message.user_id == user.id)
            .order_by(Message.created_at.desc())
            .limit(20)
            .all()
        )[::-1]
    shared_ctx = _get_shared_context(db, room_id)
    memory_ctx = _get_user_memories(db, user.id, room_id)
    messages = [{"role": "system", "content": (
        "You are Orq, an AI productivity assistant built for agentic workflows. "
        "You help users with tasks, planning, research, data analysis, and actions. "
        "You have access to CrewAI multi-agent crews, Composio app integrations "
        "(Gmail, Google Docs, Google Drive, GitHub), Snowflake data warehouse with Cortex AI, "
        "and Skyfire payments. Keep responses concise and actionable. "
        "Do NOT use horizontal rules (---) in your responses."
        + memory_ctx + shared_ctx
    )}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})
    resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    ci = _calc_cost(resp.usage)
    return _cost_result(resp.choices[0].message.content, ci["tokens"], ci["cost"])


# --- 2. Crew (CrewAI) -----------------------------------------------------

def _do_crew(message: str, user: User, db: Session, room_id: str = None) -> dict:
    msg_lower = message.lower()
    total_tokens = 0
    total_cost = 0.0

    _candidate_keywords = [
        "research candidate", "github profile", "evaluate developer",
        "candidate diligence", "technical assessment", "review github",
        "check candidate", "analyze candidate", "look at candidate",
        "research github", "github user", "candidate research",
        "look up github", "check github", "check their github",
        "look at github", "find on github", "search github",
        "github repos", "github repositories", "employee github",
        "developer profile", "their repos", "their repositories",
        "find out about", "about this candidate", "about this developer",
        "here is his github", "here is her github", "here is their github",
        "his github", "her github", "their github",
        "good fit", "qualification", "is a fit", "interview question",
        "check if", "scan github", "scan repo", "scan his",
        "scan her", "scan their", "tell me about",
        "github.com/", "github:", "github is ", "github -",
        "review their", "review his", "review her",
        "tell if", "check qualification", "evaluate this",
        "using snowflake", "using cortex", "analyze this person",
        "analyze his", "analyze her", "analyze their",
    ]
    # Also detect GitHub URLs directly in the message
    _has_github_url = "github.com/" in msg_lower
    if _has_github_url or any(kw in msg_lower for kw in _candidate_keywords):
        client = get_openai_client()
        if client:
            extract = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract GitHub and candidate information from the user's message.\n"
                        "Return JSON: {\"github_username\": \"...\", \"target_role\": \"...\", \"candidate_name\": \"...\"}\n\n"
                        "Rules for extraction:\n"
                        "- github_username: Extract the GitHub username. Look for:\n"
                        "  * URLs like 'github.com/USERNAME' or 'https://github.com/USERNAME' -> extract USERNAME\n"
                        "  * Phrases like 'github Yug-More' or 'github: SeanAminov' -> extract the username\n"
                        "  * 'his github is X' or 'github name X' -> extract X\n"
                        "  * Just a username mentioned in context of GitHub -> extract it\n"
                        "- target_role: The role/position being evaluated for. Default to 'Software Engineer' if not specified.\n"
                        "- candidate_name: The person's real name if mentioned (not their GitHub username).\n\n"
                        "Use empty string if not found. ALWAYS try to extract a github_username."
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci = _calc_cost(extract.usage)
            total_tokens += ci["tokens"]
            total_cost += ci["cost"]
            params = _safe_json(extract.choices[0].message.content)
            if params.get("github_username"):
                try:
                    result = run_candidate_research(
                        github_username=params["github_username"],
                        target_role=params.get("target_role", "Software Engineer"),
                        candidate_name=params.get("candidate_name", ""),
                    )
                    total_tokens += 8000
                    total_cost += 8000 / 1000 * _COST_PER_1K_OUTPUT
                    return _cost_result(result.get("candidate_brief", "Research completed but no brief generated."), total_tokens, total_cost)
                except Exception as e:
                    logger.error(f"[crew] candidate research error: {e}")
                    total_tokens += 500
                    total_cost += 500 / 1000 * _COST_PER_1K_OUTPUT
                    return _cost_result(f"Candidate research failed: {e}", total_tokens, total_cost)

    # Fast path: code contribution query (uses room's linked repo)
    contrib_result = _do_contribution_query(message, user, db, room_id)
    if contrib_result is not None:
        return contrib_result

    # Fast path: direct GitHub query -- user mentions a GitHub username or repo
    # but it's not a full candidate research (e.g., "tell me about SeanAminov's repos")
    _gh_direct_keywords = [
        "github", "repo ", "repos", "repository", "commit", "commits",
        "pushed", "code by", "last code", "latest project",
    ]
    if any(kw in msg_lower for kw in _gh_direct_keywords):
        result = _do_github_direct_query(message, user, db, room_id)
        if result is not None:
            return result

    if any(kw in msg_lower for kw in ["commit digest", "what was pushed", "commit summary",
                                       "commits from", "digest of commits"]):
        client = get_openai_client()
        if client:
            extract = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract from the user's message: repo (owner/repo format), author, "
                        "path_filter, since_days. Return JSON: "
                        "{\"repo\": \"owner/repo\", \"author\": \"...\", \"path_filter\": \"...\", \"since_days\": 7}. "
                        "Use null for missing fields."
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci = _calc_cost(extract.usage)
            total_tokens += ci["tokens"]
            total_cost += ci["cost"]
            params = _safe_json(extract.choices[0].message.content)
            if params.get("repo"):
                result = run_commit_digest(
                    repo=params["repo"],
                    author=params.get("author"),
                    path_filter=params.get("path_filter"),
                    since_days=params.get("since_days", 7),
                )
                # CrewAI digest runs ~3 agents; estimate ~5000 tokens
                total_tokens += 5000
                total_cost += 5000 / 1000 * _COST_PER_1K_OUTPUT
                return _cost_result(result.get("digest_markdown", "Digest generated but no content."), total_tokens, total_cost)

    if room_id:
        history = (
            db.query(Message)
            .filter(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )[::-1]
    else:
        history = (
            db.query(Message)
            .filter(Message.user_id == user.id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )[::-1]
    context = "\n".join(f"{m.role}: {m.content}" for m in history)
    shared_ctx = _get_shared_context(db, room_id)
    memory_ctx = _get_user_memories(db, user.id, room_id)
    if memory_ctx:
        context += memory_ctx
    if shared_ctx:
        context += shared_ctx
    reply = run_crew(message, context)
    total_tokens += 6000
    total_cost += 6000 / 1000 * _COST_PER_1K_OUTPUT
    return _cost_result(reply, total_tokens, total_cost)


# --- 3. Action (Composio) -------------------------------------------------

def _do_composio_action(message: str, user: User, db: Session, room_id: str = None) -> dict:
    client = get_openai_client()
    composio = get_composio_client()
    if not client:
        return _cost_result("OpenAI not configured.")
    if not composio:
        return _cost_result("Composio not configured. Set COMPOSIO_API_KEY in .env.")

    tools = get_composio_tools()
    if not tools:
        return _cost_result("No Composio tools available. Check your connected apps.")

    total_tokens = 0
    total_cost = 0.0

    # Build room context for better email/action targeting
    room_context = ""
    if room_id:
        # Get room info
        room = db.query(Room).filter(Room.id == room_id).first()
        # Get room members with emails
        members = (
            db.query(User)
            .join(RoomMember, RoomMember.user_id == User.id)
            .filter(RoomMember.room_id == room_id)
            .all()
        )
        member_list = ", ".join(f"{m.name} ({m.email})" for m in members)
        # Get recent room messages for conversation context
        room_msgs = (
            db.query(Message)
            .filter(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(30)
            .all()
        )[::-1]
        convo_lines = []
        for rm in room_msgs:
            ts = rm.created_at.strftime("%Y-%m-%d %H:%M") if rm.created_at else ""
            convo_lines.append(f"[{ts}] {rm.sender_name}: {rm.content[:200]}")
        convo_text = "\n".join(convo_lines)
        room_context = (
            f"\n\nCONTEXT -- You are in room '{room.name if room else 'Unknown'}'.\n"
            f"Room members: {member_list}\n"
            f"Recent conversation:\n{convo_text}\n\n"
            f"When the user asks to email room members or send a summary, use the REAL email addresses listed above. "
            f"Do NOT use placeholder emails like requester@example.com. "
            f"When summarizing conversations, use the actual conversation content above."
        )

    tool_names = []
    for t in tools:
        if isinstance(t, dict) and "function" in t:
            tool_names.append(t["function"]["name"])
        elif hasattr(t, "function"):
            tool_names.append(t.function.name)
    logger.info(f"[composio] {len(tools)} tools loaded: {tool_names[:10]}...")

    if room_id:
        history = (
            db.query(Message)
            .filter(Message.room_id == room_id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )[::-1]
    else:
        history = (
            db.query(Message)
            .filter(Message.user_id == user.id)
            .order_by(Message.created_at.desc())
            .limit(10)
            .all()
        )[::-1]

    shared_ctx = _get_shared_context(db, room_id)
    memory_ctx = _get_user_memories(db, user.id, room_id)
    system_prompt = (
        "You are Orq, an action executor with access to real app integrations.\n"
        "Given the user's request, call the appropriate tool to fulfill it.\n\n"
        "TOOL SELECTION RULES -- follow these strictly:\n"
        "- 'send email' / 'email someone' / 'send a message to' -> use GMAIL_SEND_EMAIL\n"
        "- 'draft email' / 'prepare email' / 'write email but don't send' -> use GMAIL_CREATE_EMAIL_DRAFT\n"
        "- 'check email' / 'read emails' / 'latest emails' / 'inbox' -> use GMAIL_FETCH_EMAILS\n"
        "- 'create doc' / 'new document' / 'write a doc' -> use GOOGLEDOCS_CREATE_DOCUMENT\n"
        "- 'list files' / 'my drive' / 'google drive' -> use GOOGLEDRIVE_LIST_FILES\n"
        "- 'commit' / 'push to github' / 'update readme' / 'create file on github' -> use GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS\n"
        "- 'list repos' / 'show repositories' -> use GITHUB_LIST_REPOSITORIES_FOR_A_USER\n"
        "- 'show commits' / 'recent commits' -> use GITHUB_LIST_COMMITS\n"
        "- 'repo details' / 'about this repo' -> use GITHUB_GET_A_REPOSITORY\n"
        "- 'schedule meeting' / 'calendar invite' / 'book a call' / 'set up an interview' / 'create event' -> use GOOGLECALENDAR_CREATE_EVENT\n"
        "- 'check calendar' / 'upcoming events' / 'find meeting' -> use GOOGLECALENDAR_FIND_EVENT\n\n"
        "IMPORTANT: When the user says 'send', ALWAYS use GMAIL_SEND_EMAIL, never GMAIL_CREATE_EMAIL_DRAFT.\n"
        "Only use the draft tool when the user explicitly asks for a draft.\n\n"
        "When the user asks to commit or push a file to GitHub, use GITHUB_CREATE_OR_UPDATE_FILE_CONTENTS.\n"
        "The owner and repo should be extracted from context or the user's message.\n\n"
        "When composing email body content, write a complete, natural message.\n"
        "Always call a tool -- do not just describe what you would do."
    ) + memory_ctx + room_context + shared_ctx

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-6:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})

    resp = client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, tools=tools, tool_choice="required",
    )
    ci = _calc_cost(resp.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    assistant_msg = resp.choices[0].message

    if not assistant_msg.tool_calls:
        return _cost_result(assistant_msg.content or "No action was needed for this request.", total_tokens, total_cost)

    results = []
    for tc in assistant_msg.tool_calls:
        slug = tc.function.name
        try:
            args = json.loads(tc.function.arguments)
        except json.JSONDecodeError:
            args = {}
        logger.info(f"[composio] executing {slug} with args: {list(args.keys())}")
        result = execute_composio_tool(slug, args)
        results.append({"tool": slug, "result": result})

    tool_call_msgs = [
        {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
        for tc in assistant_msg.tool_calls
    ]
    messages.append({"role": "assistant", "content": None, "tool_calls": tool_call_msgs})
    for i, tc in enumerate(assistant_msg.tool_calls):
        messages.append({
            "role": "tool", "tool_call_id": tc.id,
            "content": json.dumps(results[i]["result"], default=str)[:4000],
        })
    messages.append({"role": "system", "content": (
        "Summarize the result of the tool execution for the user. "
        "The action has ALREADY been completed. Report what was done, "
        "do NOT ask for confirmation or say 'would you like me to...'. "
        "The tool has already executed -- just confirm the result clearly."
    )})
    summary_resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    ci2 = _calc_cost(summary_resp.usage)
    total_tokens += ci2["tokens"]
    total_cost += ci2["cost"]
    return _cost_result(summary_resp.choices[0].message.content, total_tokens, total_cost)


# --- 4. Data (Snowflake + Cortex AI) --------------------------------------

def _do_snowflake_query(message: str, user: User, db: Session, room_id: str = None) -> dict:
    client = get_openai_client()
    conn = get_snowflake_connection()
    if not client:
        return _cost_result("OpenAI not configured.")
    if not conn:
        return _cost_result("Snowflake not configured. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in .env.")

    total_tokens = 0
    total_cost = 0.0
    memory_ctx = _get_user_memories(db, user.id, room_id)

    classify_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are a query classifier. Given the user's message, decide which "
                "Snowflake operation to use. Respond with ONLY one of these labels:\n"
                "  SENTIMENT  - if the user wants sentiment analysis of text\n"
                "  TRANSLATE  - if the user wants text translated to another language\n"
                "  SUMMARIZE  - if the user wants text summarized\n"
                "  SQL        - if the user wants to query data from database tables\n"
                "Respond with JUST the label, nothing else."
            )},
            {"role": "user", "content": message},
        ],
    )
    ci = _calc_cost(classify_resp.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    operation = classify_resp.choices[0].message.content.strip().upper()
    logger.info(f"[snowflake] classified as: {operation}")

    try:
        cur = conn.cursor()

        if "SENTIMENT" in operation:
            text = _extract_text_for_cortex(client, message, "sentiment analysis")
            total_tokens += 200; total_cost += 200 / 1000 * _COST_PER_1K_OUTPUT  # extract call estimate
            sql = f"SELECT SNOWFLAKE.CORTEX.SENTIMENT('{_escape_sql(text)}')"
            cur.execute(sql)
            score = cur.fetchone()[0]
            cur.close()
            sentiment = "positive" if float(score) > 0.1 else "negative" if float(score) < -0.1 else "neutral"
            return _cost_result(
                f"**Sentiment Analysis**\n\n"
                f"Text: \"{text[:200]}{'...' if len(text) > 200 else ''}\"\n\n"
                f"Score: `{score}` ({sentiment})\n\n"
                f"_Scale: -1.0 (very negative) to +1.0 (very positive)_",
                total_tokens, total_cost,
            )

        elif "TRANSLATE" in operation:
            extract_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract the text to translate and the target language from "
                        "the user's message. Respond as JSON: "
                        "{\"text\": \"...\", \"target_lang\": \"en|es|fr|de|ja|ko|zh|pt|it|ru\"}"
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci2 = _calc_cost(extract_resp.usage)
            total_tokens += ci2["tokens"]
            total_cost += ci2["cost"]
            parsed = _safe_json(extract_resp.choices[0].message.content)
            text = parsed.get("text", message)
            lang = parsed.get("target_lang", "en")
            sql = f"SELECT SNOWFLAKE.CORTEX.TRANSLATE('{_escape_sql(text)}', '', '{lang}')"
            cur.execute(sql)
            translated = cur.fetchone()[0]
            cur.close()
            return _cost_result(
                f"**Translation** (-> {lang})\n\n"
                f"Original: \"{text[:300]}\"\n\n"
                f"Translated: \"{translated}\"",
                total_tokens, total_cost,
            )

        elif "SUMMARIZE" in operation:
            text = _extract_text_for_cortex(client, message, "summarization")
            total_tokens += 200; total_cost += 200 / 1000 * _COST_PER_1K_OUTPUT
            sql = f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{_escape_sql(text)}')"
            cur.execute(sql)
            summary = cur.fetchone()[0]
            cur.close()
            return _cost_result(f"**Summary**\n\n{summary}", total_tokens, total_cost)

        else:
            sql_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "You are a Snowflake SQL expert. Convert the user's natural "
                        "language question into a single SELECT query. Return ONLY "
                        "the SQL -- no explanation, no markdown fences. "
                        "Available databases: POLICY_DB, SNOWFLAKE, USER$USER. "
                        "Default schema: PUBLIC. Use LIMIT 50 for safety."
                        + memory_ctx
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci3 = _calc_cost(sql_resp.usage)
            total_tokens += ci3["tokens"]
            total_cost += ci3["cost"]
            sql = sql_resp.choices[0].message.content.strip().strip("`").strip()
            logger.info(f"[snowflake] executing SQL: {sql[:200]}")
            cur.execute(sql)
            rows = cur.fetchmany(50)
            cols = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            if not rows:
                return _cost_result(f"Query returned no results.\n\n`{sql}`", total_tokens, total_cost)
            header = " | ".join(cols)
            lines = [header, "-" * len(header)]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            table = "\n".join(lines)
            return _cost_result(f"```\n{table}\n```\n\nSQL: `{sql}`", total_tokens, total_cost)

    except Exception as e:
        return _cost_result(f"Snowflake error: {e}", total_tokens, total_cost)


def _extract_text_for_cortex(client, message: str, task: str) -> str:
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                f"Extract the text the user wants used for {task}. "
                "Return ONLY the text itself, nothing else. "
                "If the whole message IS the text, return it as-is."
            )},
            {"role": "user", "content": message},
        ],
    )
    return resp.choices[0].message.content.strip()


def _escape_sql(text: str) -> str:
    return text.replace("'", "''").replace("\\", "\\\\")


def _safe_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# --- 5a. Research (Skyfire + BuildShip companyResearcher) -------------------

SKYFIRE_RESEARCH_SERVICE_ID = "b07adb24-85fc-4b4d-92ae-54571a7bdfbf"
SKYFIRE_RESEARCH_ENDPOINT = "https://ct7rdx.buildship.run/executeTool/U40tJouoY9wAaIhk8Z37/22e5a0a4-5ead-442b-ab12-4ece693ca2d9"

def _do_skyfire_research(message: str, user: User, db: Session, room_id: str = None) -> dict:
    """Company research via Skyfire-paid BuildShip companyResearcher service.
    Accepts an email or domain and returns structured company info."""
    if not SKYFIRE_API_KEY:
        return _cost_result("Skyfire not configured. Set SKYFIRE_API_KEY in .env.")
    client = get_openai_client()
    if not client:
        return _cost_result("OpenAI not configured.")

    total_tokens = 0
    total_cost = 0.0
    memory_ctx = _get_user_memories(db, user.id, room_id)

    # Extract email or domain from the user's message using LLM
    extract_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "Extract an email address or company domain from the user's message. "
                "Return ONLY the email or domain, nothing else. "
                "If the message contains a person's name, try to derive their company from context. "
                "If you cannot find an email or domain, return 'NONE'."
                + memory_ctx
            )},
            {"role": "user", "content": message},
        ],
    )
    ci = _calc_cost(extract_resp.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    email_or_domain = extract_resp.choices[0].message.content.strip()
    logger.info(f"[skyfire-research] extracted: {email_or_domain}")

    if email_or_domain == "NONE" or len(email_or_domain) < 3:
        return _cost_result(
            "**Company Research**\n\n"
            "I need an email address or company domain to research.\n\n"
            "Try: `@research google.com` or `@research john@acme.com`",
            total_tokens, total_cost,
        )

    sf_headers = {"skyfire-api-key": SKYFIRE_API_KEY, "Content-Type": "application/json"}

    try:
        import time as _time
        # Step 1: Create a Skyfire pay token for the companyResearcher service
        token_resp = requests.post(
            f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
            json={
                "type": "pay",
                "tokenAmount": "0.01",
                "sellerServiceId": SKYFIRE_RESEARCH_SERVICE_ID,
                "expiresAt": int(_time.time()) + 300,
            },
            timeout=10,
        )
        if not token_resp.ok:
            err = token_resp.text[:200]
            return _cost_result(
                f"**Company Research**\n\n"
                f"Could not create Skyfire payment token (status {token_resp.status_code}).\n\n"
                f"Error: {err}\n\n"
                f"_Ensure your Skyfire wallet is funded at [skyfire.xyz](https://skyfire.xyz)._",
                total_tokens, total_cost,
            )

        token_data = token_resp.json()
        token_jwt = token_data.get("token") or token_data.get("data", {}).get("token", "")
        logger.info(f"[skyfire-research] token created: {token_jwt[:30]}...")

        # Step 2: Call the BuildShip companyResearcher service
        service_resp = requests.post(
            SKYFIRE_RESEARCH_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "skyfire_kya_pay_token": token_jwt,
            },
            json={"emailOrDomain": email_or_domain},
            timeout=30,
        )

        if service_resp.ok:
            data = service_resp.json() if service_resp.headers.get("content-type", "").startswith("application/json") else {"raw": service_resp.text}
            output = data.get("output", data)

            # Format the company info nicely
            if isinstance(output, dict):
                parts = [f"**Company Research: {email_or_domain}**\n"]
                for k, v in output.items():
                    if v and v != "N/A":
                        label = k.replace("_", " ").title()
                        parts.append(f"- **{label}**: {v}")
                parts.append(f"\n_Powered by Skyfire + BuildShip | Cost: $0.01_")
                return _cost_result("\n".join(parts), total_tokens, total_cost)
            else:
                return _cost_result(
                    f"**Company Research: {email_or_domain}**\n\n{output}\n\n"
                    f"_Powered by Skyfire + BuildShip | Cost: $0.01_",
                    total_tokens, total_cost,
                )
        else:
            return _cost_result(
                f"**Company Research**\n\n"
                f"Service returned status {service_resp.status_code}.\n\n"
                f"Response: {service_resp.text[:300]}\n\n"
                f"_The BuildShip service may be temporarily unavailable._",
                total_tokens, total_cost,
            )

    except requests.exceptions.Timeout:
        return _cost_result("Company research request timed out. The service may be temporarily unavailable.", total_tokens, total_cost)
    except Exception as e:
        return _cost_result(f"Company research error: {e}", total_tokens, total_cost)


# --- 5b. Clean (Skyfire + BuildShip aiSlopCleaner) -------------------------

SKYFIRE_CLEAN_SERVICE_ID = "2236ee9f-339f-4d77-a22e-b3df3df2f34a"
SKYFIRE_CLEAN_ENDPOINT = "https://ct7rdx.buildship.run/executeTool/xs2eHScGZnrjzDiO49pk/ff20942c-670d-4a26-843a-5b0af0894a85"

def _do_skyfire_clean(message: str, user: User, db: Session, room_id: str = None) -> dict:
    """Refine AI-generated text via Skyfire-paid BuildShip aiSlopCleaner service.
    Takes messy AI-generated transcript and returns clean, human-like text."""
    if not SKYFIRE_API_KEY:
        return _cost_result("Skyfire not configured. Set SKYFIRE_API_KEY in .env.")

    total_tokens = 0
    total_cost = 0.0

    transcript = message.strip()
    if len(transcript) < 10:
        return _cost_result(
            "**AI Text Cleaner**\n\n"
            "I need some AI-generated text to clean up.\n\n"
            "Try: `@clean <paste your AI-generated text here>`",
            total_tokens, total_cost,
        )

    sf_headers = {"skyfire-api-key": SKYFIRE_API_KEY, "Content-Type": "application/json"}

    try:
        import time as _time
        # Step 1: Create a Skyfire pay token for the aiSlopCleaner service
        token_resp = requests.post(
            f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
            json={
                "type": "pay",
                "tokenAmount": "0.03",
                "sellerServiceId": SKYFIRE_CLEAN_SERVICE_ID,
                "expiresAt": int(_time.time()) + 300,
            },
            timeout=10,
        )
        if not token_resp.ok:
            err = token_resp.text[:200]
            return _cost_result(
                f"**AI Text Cleaner**\n\n"
                f"Could not create Skyfire payment token (status {token_resp.status_code}).\n\n"
                f"Error: {err}\n\n"
                f"_Ensure your Skyfire wallet is funded at [skyfire.xyz](https://skyfire.xyz)._",
                total_tokens, total_cost,
            )

        token_data = token_resp.json()
        token_jwt = token_data.get("token") or token_data.get("data", {}).get("token", "")
        logger.info(f"[skyfire-clean] token created: {token_jwt[:30]}...")

        # Step 2: Call the BuildShip aiSlopCleaner service
        service_resp = requests.post(
            SKYFIRE_CLEAN_ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "skyfire_kya_pay_token": token_jwt,
            },
            json={"transcript": transcript},
            timeout=30,
        )

        if service_resp.ok:
            # Response is a string
            cleaned = service_resp.text
            # Try to parse as JSON string if it's wrapped
            try:
                cleaned = json.loads(cleaned)
                if isinstance(cleaned, dict):
                    cleaned = cleaned.get("output", cleaned.get("result", str(cleaned)))
            except (json.JSONDecodeError, TypeError):
                pass

            return _cost_result(
                f"**Cleaned Text** _(via Skyfire + BuildShip)_\n\n{cleaned}\n\n"
                f"_AI slop removed | Cost: $0.03_",
                total_tokens, total_cost,
            )
        else:
            return _cost_result(
                f"**AI Text Cleaner**\n\n"
                f"Service returned status {service_resp.status_code}.\n\n"
                f"Response: {service_resp.text[:300]}\n\n"
                f"_The BuildShip service may be temporarily unavailable._",
                total_tokens, total_cost,
            )

    except requests.exceptions.Timeout:
        return _cost_result("Text cleaning request timed out. The service may be temporarily unavailable.", total_tokens, total_cost)
    except Exception as e:
        return _cost_result(f"Text cleaning error: {e}", total_tokens, total_cost)


# --- 5c. Pay (Skyfire) ----------------------------------------------------

def _do_skyfire_payment(message: str, user: User, db: Session, room_id: str = None) -> dict:
    if not SKYFIRE_API_KEY:
        return _cost_result("Skyfire not configured. Set SKYFIRE_API_KEY in .env.")
    client = get_openai_client()
    if not client:
        return _cost_result("OpenAI not configured.")

    total_tokens = 0
    total_cost = 0.0
    memory_ctx = _get_user_memories(db, user.id, room_id)

    classify_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are a payment classifier. Given the user's message, decide "
                "which Skyfire operation to perform. Respond with ONLY one label:\n"
                "  BALANCE   - check wallet or balance\n"
                "  LLM_PROXY - use a Skyfire paid service (company research, AI query)\n"
                "  TOKEN     - create a payment token or session\n"
                "  PAY       - send a payment or transfer funds\n"
                "  INFO      - explain Skyfire or its capabilities\n"
                "Respond with JUST the label."
            )},
            {"role": "user", "content": message},
        ],
    )
    ci = _calc_cost(classify_resp.usage)
    total_tokens += ci["tokens"]
    total_cost += ci["cost"]
    operation = classify_resp.choices[0].message.content.strip().upper()
    logger.info(f"[skyfire] classified as: {operation}")

    sf_headers = {"skyfire-api-key": SKYFIRE_API_KEY, "Content-Type": "application/json"}

    try:
        if "BALANCE" in operation:
            balance_resp = requests.get(
                f"{SKYFIRE_BASE_URL}/api/v1/agents/balance", headers=sf_headers, timeout=10,
            )
            if balance_resp.ok:
                bal = balance_resp.json()
                bal_data = bal.get("data", bal)
                available = bal_data.get("balance", bal_data.get("availableBalance", "N/A"))
                currency = bal_data.get("currency", "USD")
                return _cost_result(
                    f"**Skyfire Wallet**\n\n"
                    f"Balance: **{available} {currency}**\n\n"
                    f"_Wallet is active and ready for agent transactions._",
                    total_tokens, total_cost,
                )
            return _cost_result(
                f"**Skyfire Wallet**\n\nCould not retrieve balance (status {balance_resp.status_code}).\n\n"
                f"_Check your SKYFIRE_API_KEY in .env or visit [skyfire.xyz](https://skyfire.xyz)._",
                total_tokens, total_cost,
            )

        elif "LLM_PROXY" in operation:
            # Use Skyfire-paid BuildShip companyResearcher as the default paid AI service
            import time as _time
            token_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json={
                    "type": "pay",
                    "tokenAmount": "0.01",
                    "sellerServiceId": SKYFIRE_RESEARCH_SERVICE_ID,
                    "expiresAt": int(_time.time()) + 300,
                },
                timeout=10,
            )
            if token_resp.ok:
                token_data = token_resp.json()
                token_jwt = token_data.get("token") or token_data.get("data", {}).get("token", "")
                # Try calling companyResearcher with the query as a domain/email
                try:
                    svc_resp = requests.post(
                        SKYFIRE_RESEARCH_ENDPOINT,
                        headers={"Content-Type": "application/json", "skyfire_kya_pay_token": token_jwt},
                        json={"emailOrDomain": message.split()[-1] if message.strip() else "skyfire.xyz"},
                        timeout=30,
                    )
                    if svc_resp.ok:
                        data = svc_resp.json() if svc_resp.headers.get("content-type", "").startswith("application/json") else {"raw": svc_resp.text}
                        output = data.get("output", data)
                        if isinstance(output, dict):
                            parts = ["**Skyfire AI Response** _(via BuildShip companyResearcher)_\n"]
                            for k, v in output.items():
                                if v and v != "N/A":
                                    parts.append(f"- **{k.replace('_', ' ').title()}**: {v}")
                            parts.append(f"\n_Paid via Skyfire token | Cost: $0.01_")
                            return _cost_result("\n".join(parts), total_tokens, total_cost)
                        return _cost_result(
                            f"**Skyfire AI Response** _(via BuildShip)_\n\n{output}\n\n_Paid via Skyfire | Cost: $0.01_",
                            total_tokens, total_cost,
                        )
                except Exception:
                    pass

            # Fallback to direct OpenAI
            fallback = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
                    {"role": "user", "content": message},
                ],
            )
            ci2 = _calc_cost(fallback.usage)
            total_tokens += ci2["tokens"]
            total_cost += ci2["cost"]
            return _cost_result(
                f"**Skyfire AI Response** _(via OpenAI fallback)_\n\n{fallback.choices[0].message.content}\n\n"
                f"_Note: Skyfire paid services require funded wallet. Response served via direct OpenAI as fallback._",
                total_tokens, total_cost,
            )

        elif "TOKEN" in operation:
            import time as _time
            parse_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract token creation details from the user's message. "
                        "Return JSON: {\"type\": \"kya|pay|kya+pay\", \"amount\": \"0.10\", "
                        "\"seller_id\": \"service-uuid\"}. "
                        "Known services: companyResearcher (b07adb24-85fc-4b4d-92ae-54571a7bdfbf, $0.01), "
                        "aiSlopCleaner (2236ee9f-339f-4d77-a22e-b3df3df2f34a, $0.03). "
                        "Default: type=pay, amount=0.01, seller_id=b07adb24-85fc-4b4d-92ae-54571a7bdfbf"
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci_t = _calc_cost(parse_resp.usage)
            total_tokens += ci_t["tokens"]
            total_cost += ci_t["cost"]
            tok_params = _safe_json(parse_resp.choices[0].message.content)
            token_type = tok_params.get("type", "pay")
            token_amount = tok_params.get("amount", "0.01")
            seller_id = tok_params.get("seller_id", SKYFIRE_RESEARCH_SERVICE_ID)
            token_body = {
                "type": token_type,
                "tokenAmount": str(token_amount),
                "sellerServiceId": seller_id,
                "expiresAt": int(_time.time()) + 300,
            }
            token_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json=token_body, timeout=10,
            )
            if token_resp.ok:
                return _cost_result(
                    f"**Skyfire Token Created**\n\n"
                    f"Type: `{token_type}`\nAmount: `{token_amount} USD`\nService: `{seller_id[:20]}...`\n\n"
                    f"```json\n{json.dumps(token_resp.json(), indent=2, default=str)}\n```",
                    total_tokens, total_cost,
                )
            err_msg = "Unknown error"
            try:
                err_msg = token_resp.json().get("message", token_resp.text[:200])
            except Exception:
                err_msg = token_resp.text[:200]
            return _cost_result(
                f"**Skyfire Token Request**\n\n"
                f"Type: `{token_type}` | Amount: `{token_amount} USD` | Seller: `{seller_url}`\n\n"
                f"Status: {token_resp.status_code} -- {err_msg}\n\n"
                f"_Token creation requires a funded Skyfire wallet at [skyfire.xyz](https://skyfire.xyz)._",
                total_tokens, total_cost,
            )

        elif "PAY" in operation:
            import time as _time
            parse_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract payment details from the user's message. "
                        "Return JSON: {\"amount\": \"0.01\", \"service_id\": \"uuid\", "
                        "\"description\": \"string\"}. "
                        "Known services: companyResearcher (b07adb24-85fc-4b4d-92ae-54571a7bdfbf, $0.01), "
                        "aiSlopCleaner (2236ee9f-339f-4d77-a22e-b3df3df2f34a, $0.03). "
                        "Default service: b07adb24-85fc-4b4d-92ae-54571a7bdfbf"
                        + memory_ctx
                    )},
                    {"role": "user", "content": message},
                ],
            )
            ci3 = _calc_cost(parse_resp.usage)
            total_tokens += ci3["tokens"]
            total_cost += ci3["cost"]
            pay_intent = _safe_json(parse_resp.choices[0].message.content)
            amount = str(pay_intent.get("amount", "0.01"))
            service_id = pay_intent.get("service_id", SKYFIRE_RESEARCH_SERVICE_ID)
            pay_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json={
                    "type": "pay",
                    "tokenAmount": amount,
                    "sellerServiceId": service_id,
                    "expiresAt": int(_time.time()) + 300,
                },
                timeout=15,
            )
            if pay_resp.ok:
                return _cost_result(
                    f"**Payment Sent via Skyfire**\n\n"
                    f"Amount: **{amount} USD**\n"
                    f"Service: `{service_id[:20]}...`\n"
                    f"Description: {pay_intent.get('description', 'N/A')}\n\n"
                    f"```json\n{json.dumps(pay_resp.json(), indent=2, default=str)}\n```",
                    total_tokens, total_cost,
                )
            return _cost_result(
                f"**Payment Intent**\n\n"
                f"Amount: **{amount} USD**\n"
                f"Service: `{service_id[:20]}...`\n"
                f"Description: {pay_intent.get('description', 'N/A')}\n\n"
                f"Status: {pay_resp.status_code}\n\n"
                f"_Full payments require a funded Skyfire wallet at [skyfire.xyz](https://skyfire.xyz)._",
                total_tokens, total_cost,
            )

        else:
            # INFO: check wallet and show capabilities
            balance_resp = requests.get(
                f"{SKYFIRE_BASE_URL}/api/v1/agents/balance", headers=sf_headers, timeout=5,
            )
            bal_str = "Unavailable"
            if balance_resp.ok:
                bal = balance_resp.json()
                bal_data = bal.get("data", bal)
                bal_str = f"{bal_data.get('balance', bal_data.get('availableBalance', 'N/A'))} USD"
            return _cost_result(
                f"**Skyfire** -- AI-Native Payment Protocol\n\n"
                f"Wallet Balance: **{bal_str}**\n\n"
                f"Skyfire enables autonomous agent commerce:\n"
                f"- **Company Research** (`@research`): Get structured company info from email/domain ($0.01)\n"
                f"- **AI Text Cleaner** (`@clean`): Refine AI-generated text to sound natural ($0.03)\n"
                f"- **Payment tokens**: Three types -- `kya` (identity), `pay` (payment), `kya+pay` (both)\n"
                f"- **Agent wallets**: USDC-based balance with real-time settlement\n\n"
                f"Try: `@pay check balance`, `@research google.com`, `@clean <paste AI text>`",
                total_tokens, total_cost,
            )

    except requests.exceptions.Timeout:
        return _cost_result("Skyfire request timed out. The service may be temporarily unavailable.", total_tokens, total_cost)
    except Exception as e:
        return _cost_result(f"Skyfire error: {e}", total_tokens, total_cost)


# ---------------------------------------------------------------------------
# Composio management
# ---------------------------------------------------------------------------

@app.get("/api/composio/status")
def composio_status(user: User = Depends(get_current_user)):
    composio = get_composio_client()
    if not composio:
        return {"connected": False, "apps": [], "error": "Composio not configured"}
    try:
        connections = composio.connected_accounts.list(user_id="parallel-sean")
        apps = list(set(c.appName for c in connections if hasattr(c, "appName")))
        return {"connected": True, "apps": apps, "count": len(connections)}
    except Exception as e:
        logger.error(f"composio status error: {e}")
        return {"connected": True, "apps": ["gmail", "googledocs", "googledrive"], "note": "fallback list"}

# ---------------------------------------------------------------------------
# Runs -- advanced multi-agent workflows (kept for RunPanel)
# ---------------------------------------------------------------------------

@app.post("/api/runs/candidate-research")
def run_candidate_research_endpoint(body: CandidateResearchBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"[run] candidate research for @{body.github_username} -> {body.target_role}")
    try:
        result = run_candidate_research(
            github_username=body.github_username, target_role=body.target_role,
            candidate_name=body.candidate_name, company_context=body.company_context,
            resume_text=body.resume_text, generate_outreach=body.generate_outreach,
        )
    except Exception as e:
        logger.error(f"[run] candidate research error: {e}")
        raise HTTPException(500, f"Candidate research failed: {e}")
    db.add(Activity(
        id=str(uuid.uuid4()), user_id=user.id, user_name=user.name,
        summary=f"Candidate Research: {body.github_username} for {body.target_role}",
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return result

@app.post("/api/runs/commit-digest")
def run_commit_digest_endpoint(body: CommitDigestBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(f"[run] commit digest for {body.repo} (author={body.author})")
    try:
        result = run_commit_digest(
            repo=body.repo, author=body.author, path_filter=body.path_filter,
            since_days=body.since_days, max_commits=body.max_commits,
            email_to=body.email_to, create_doc=body.create_doc,
        )
    except Exception as e:
        logger.error(f"[run] commit digest error: {e}")
        raise HTTPException(500, f"Commit digest failed: {e}")
    db.add(Activity(
        id=str(uuid.uuid4()), user_id=user.id, user_name=user.name,
        summary=f"Commit Digest: {body.repo} ({body.author or 'all'}) - {body.since_days}d",
        created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return result

# ---------------------------------------------------------------------------
# Legacy endpoints (backward compat)
# ---------------------------------------------------------------------------

@app.post("/api/chat")
def chat(body: ChatBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    db.add(Message(
        id=str(uuid.uuid4()), user_id=user.id,
        sender_id=user.id, sender_name=user.name,
        role="user", content=body.message, created_at=now,
    ))
    db.commit()
    handlers = {"chat": _do_chat, "crew": _do_crew, "action": _do_composio_action, "data": _do_snowflake_query, "pay": _do_skyfire_payment, "research": _do_skyfire_research, "clean": _do_skyfire_clean}
    handler = handlers.get(body.mode, _do_chat)
    try:
        result = handler(body.message, user, db, None)
        reply = result.get("reply", str(result)) if isinstance(result, dict) else str(result)
    except Exception as e:
        logger.error(f"[{body.mode}] {e}")
        reply = f"Error in {body.mode} mode: {e}"
    db.add(Message(
        id=str(uuid.uuid4()), user_id=user.id,
        sender_id="assistant", sender_name="Orq",
        role="assistant", content=reply, created_at=datetime.now(timezone.utc),
    ))
    db.commit()
    return {"reply": reply, "mode": body.mode}

@app.delete("/api/messages")
def clear_messages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(Message).filter(Message.user_id == user.id).delete()
    db.commit()
    return {"cleared": count}

@app.delete("/api/activity")
def clear_activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = db.query(Activity).filter(Activity.user_id == user.id).delete()
    db.commit()
    return {"cleared": count}

@app.get("/api/messages")
def get_messages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    msgs = db.query(Message).filter(Message.user_id == user.id).order_by(Message.created_at.asc()).limit(100).all()
    return [
        {"id": m.id, "sender_id": m.sender_id, "sender_name": m.sender_name,
         "role": m.role, "content": m.content, "created_at": str(m.created_at)}
        for m in msgs
    ]

@app.get("/api/activity")
def get_activity(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    acts = db.query(Activity).order_by(Activity.created_at.desc()).limit(30).all()
    return [{"id": a.id, "user_name": a.user_name, "summary": a.summary, "created_at": str(a.created_at)} for a in acts]

# ---------------------------------------------------------------------------
# Memory API
# ---------------------------------------------------------------------------

@app.get("/api/memories")
def list_memories(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List user's memories."""
    memories = (
        db.query(Memory)
        .filter(Memory.user_id == user.id)
        .order_by(Memory.updated_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": m.id, "category": m.category, "subject": m.subject,
            "key": m.key, "value": m.value, "room_id": m.room_id,
            "created_at": str(m.created_at), "updated_at": str(m.updated_at),
        }
        for m in memories
    ]

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Forget a specific memory."""
    mem = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user.id).first()
    if not mem:
        raise HTTPException(404, "Memory not found")
    db.delete(mem)
    db.commit()
    return {"ok": True, "deleted": memory_id}

# ---------------------------------------------------------------------------
# Workflow API
# ---------------------------------------------------------------------------

@app.post("/api/workflows")
def create_workflow(body: WorkflowCreateBody, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new custom workflow."""
    # Validate trigger doesn't clash with builtins
    builtins = {"orq", "crew", "action", "data", "pay", "summary"}
    if body.trigger.lower() in builtins:
        raise HTTPException(400, f"Trigger '@{body.trigger}' is reserved. Choose a different name.")
    # Check for duplicate trigger for this user
    existing = db.query(Workflow).filter(
        Workflow.trigger.ilike(body.trigger),
        Workflow.owner_id == user.id,
    ).first()
    if existing:
        raise HTTPException(409, f"You already have a workflow with trigger '@{body.trigger}'.")
    now = datetime.now(timezone.utc)
    wf_id = str(uuid.uuid4())
    steps_json = json.dumps([{"type": s.type, "prompt": s.prompt, "tool": s.tool} for s in body.steps])
    db.add(Workflow(
        id=wf_id, name=body.name, trigger=body.trigger,
        description=body.description, steps=steps_json,
        owner_id=user.id, room_id=body.room_id,
        is_active="true", created_at=now,
    ))
    db.commit()
    return {"id": wf_id, "name": body.name, "trigger": body.trigger}

@app.get("/api/workflows")
def list_workflows(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List user's workflows + shared room workflows they belong to."""
    user_room_ids = [m.room_id for m in db.query(RoomMember).filter(RoomMember.user_id == user.id).all()]
    wf_filter = Workflow.owner_id == user.id
    if user_room_ids:
        wf_filter = wf_filter | Workflow.room_id.in_(user_room_ids)
    workflows = (
        db.query(Workflow)
        .filter(wf_filter)
        .order_by(Workflow.created_at.desc())
        .limit(50)
        .all()
    )
    results = []
    for w in workflows:
        try:
            steps = json.loads(w.steps) if w.steps else []
        except json.JSONDecodeError:
            steps = []
        results.append({
            "id": w.id, "name": w.name, "trigger": w.trigger,
            "description": w.description, "steps": steps,
            "owner_id": w.owner_id, "room_id": w.room_id,
            "is_active": w.is_active, "created_at": str(w.created_at),
        })
    return results

@app.delete("/api/workflows/{workflow_id}")
def delete_workflow(workflow_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete a workflow."""
    wf = db.query(Workflow).filter(Workflow.id == workflow_id, Workflow.owner_id == user.id).first()
    if not wf:
        raise HTTPException(404, "Workflow not found")
    db.delete(wf)
    db.commit()
    return {"ok": True, "deleted": workflow_id}

@app.get("/api/workflows/triggers")
def list_workflow_triggers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List active workflow triggers for autocomplete."""
    user_room_ids = [m.room_id for m in db.query(RoomMember).filter(RoomMember.user_id == user.id).all()]
    wf_filter = Workflow.owner_id == user.id
    if user_room_ids:
        wf_filter = wf_filter | Workflow.room_id.in_(user_room_ids)
    workflows = (
        db.query(Workflow)
        .filter(Workflow.is_active == "true", wf_filter)
        .all()
    )
    return [
        {"trigger": w.trigger, "name": w.name, "description": w.description or ""}
        for w in workflows
    ]

# ---------------------------------------------------------------------------
# Tools status + Health
# ---------------------------------------------------------------------------

@app.get("/api/tools/status")
def tools_status(user: User = Depends(get_current_user)):
    return {
        "crewai":    {"active": True, "label": "CrewAI", "description": "Multi-agent orchestration"},
        "composio":  {"active": get_composio_client() is not None, "label": "Composio", "description": "Gmail, Docs, Drive, Calendar, GitHub"},
        "snowflake": {"active": get_snowflake_connection() is not None, "label": "Snowflake", "description": "Cortex AI (NLP)"},
        "skyfire":   {"active": SKYFIRE_API_KEY is not None, "label": "Skyfire", "description": "AI payments"},
        "openai":    {"active": get_openai_client() is not None, "label": "OpenAI", "description": f"LLM ({OPENAI_MODEL})"},
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "orq"}
