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
from models import User, UserCredential, Message, Activity, Room, RoomMember, AgentRun
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

    # classify intent -- use hint if provided and valid
    valid_intents = {"CREW", "ACTION", "DATA", "PAY", "CHAT"}
    hint_map = {"SUMMARY": "DATA"}  # @summary routes to Snowflake Cortex

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
        "CHAT":   _do_chat,
        "CREW":   _do_crew,
        "ACTION": _do_composio_action,
        "DATA":   _do_snowflake_query,
        "PAY":    _do_skyfire_payment,
    }
    handler = handlers.get(intent, _do_chat)

    try:
        reply = handler(message, user, db)
        status = "completed"
    except Exception as e:
        logger.error(f"[room:{room_id}] {intent} error: {e}")
        reply = f"Error: {e}"
        status = "failed"

    # update agent run
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if run:
        run.status = status
        run.summary = reply[:500] if reply else ""
        run.completed_at = datetime.now(timezone.utc)

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
    return {"reply": reply, "intent": intent.lower(), "run_id": run_id}

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
    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "Classify the user's intent into exactly one label. Respond with ONLY the label.\n\n"
                "CREW - complex multi-step task, research, analysis, multi-agent work, "
                "candidate research, commit digest, anything needing multiple agents\n"
                "ACTION - send email, draft email, check emails, create Google Doc, "
                "list Google Drive files (Google/Composio integrations)\n"
                "DATA - sentiment analysis, translation, text summarization, "
                "data queries (Snowflake/Cortex NLP)\n"
                "PAY - Skyfire payments, balance check, payment tokens, "
                "pay-per-query AI, anything about Skyfire\n"
                "CHAT - general conversation, questions, help, explanations, brainstorming\n\n"
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
#  MODE HANDLERS (unchanged logic from previous version)
# ===========================================================================

# --- 1. Chat (OpenAI) -----------------------------------------------------

def _do_chat(message: str, user: User, db: Session) -> str:
    client = get_openai_client()
    if not client:
        return "OpenAI is not configured. Set OPENAI_API_KEY in .env."
    history = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .limit(20)
        .all()
    )[::-1]
    messages = [{"role": "system", "content": (
        "You are Orq, an AI productivity assistant built for agentic workflows. "
        "You help users with tasks, planning, research, data analysis, and actions. "
        "You have access to CrewAI multi-agent crews, Composio app integrations "
        "(Gmail, Google Docs, Google Drive), Snowflake data warehouse with Cortex AI, "
        "and Skyfire payments. Keep responses concise and actionable."
    )}]
    for m in history:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})
    resp = client.chat.completions.create(model=OPENAI_MODEL, messages=messages)
    return resp.choices[0].message.content


# --- 2. Crew (CrewAI) -----------------------------------------------------

def _do_crew(message: str, user: User, db: Session) -> str:
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in ["research candidate", "github profile", "evaluate developer",
                                       "candidate diligence", "technical assessment", "review github"]):
        client = get_openai_client()
        if client:
            extract = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract from the user's message: github_username, target_role, candidate_name. "
                        "Return JSON: {\"github_username\": \"...\", \"target_role\": \"...\", \"candidate_name\": \"...\"}. "
                        "Use empty string if not found."
                    )},
                    {"role": "user", "content": message},
                ],
            )
            params = _safe_json(extract.choices[0].message.content)
            if params.get("github_username"):
                result = run_candidate_research(
                    github_username=params["github_username"],
                    target_role=params.get("target_role", "Software Engineer"),
                    candidate_name=params.get("candidate_name", ""),
                )
                return result.get("candidate_brief", "Research completed but no brief generated.")

    if any(kw in msg_lower for kw in ["commit digest", "what was pushed", "commit summary",
                                       "code changes", "what did", "commits from"]):
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
            params = _safe_json(extract.choices[0].message.content)
            if params.get("repo"):
                result = run_commit_digest(
                    repo=params["repo"],
                    author=params.get("author"),
                    path_filter=params.get("path_filter"),
                    since_days=params.get("since_days", 7),
                )
                return result.get("digest_markdown", "Digest generated but no content.")

    history = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )[::-1]
    context = "\n".join(f"{m.role}: {m.content}" for m in history)
    return run_crew(message, context)


# --- 3. Action (Composio) -------------------------------------------------

def _do_composio_action(message: str, user: User, db: Session) -> str:
    client = get_openai_client()
    composio = get_composio_client()
    if not client:
        return "OpenAI not configured."
    if not composio:
        return "Composio not configured. Set COMPOSIO_API_KEY in .env."

    tools = get_composio_tools()
    if not tools:
        return "No Composio tools available. Check your connected apps."

    tool_names = []
    for t in tools:
        if isinstance(t, dict) and "function" in t:
            tool_names.append(t["function"]["name"])
        elif hasattr(t, "function"):
            tool_names.append(t.function.name)
    logger.info(f"[composio] {len(tools)} tools loaded: {tool_names[:10]}...")

    history = (
        db.query(Message)
        .filter(Message.user_id == user.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )[::-1]

    system_prompt = (
        "You are Orq, an action executor with access to real app integrations.\n"
        "Given the user's request, call the appropriate tool to fulfill it.\n\n"
        "TOOL SELECTION RULES -- follow these strictly:\n"
        "- 'send email' / 'email someone' / 'send a message to' -> use GMAIL_SEND_EMAIL\n"
        "- 'draft email' / 'prepare email' / 'write email but don't send' -> use GMAIL_CREATE_EMAIL_DRAFT\n"
        "- 'check email' / 'read emails' / 'latest emails' / 'inbox' -> use GMAIL_FETCH_EMAILS\n"
        "- 'create doc' / 'new document' / 'write a doc' -> use GOOGLEDOCS_CREATE_DOCUMENT\n"
        "- 'list files' / 'my drive' / 'google drive' -> use GOOGLEDRIVE_LIST_FILES\n\n"
        "IMPORTANT: When the user says 'send', ALWAYS use GMAIL_SEND_EMAIL, never GMAIL_CREATE_EMAIL_DRAFT.\n"
        "Only use the draft tool when the user explicitly asks for a draft.\n\n"
        "When composing email body content, write a complete, natural message.\n"
        "Always call a tool -- do not just describe what you would do."
    )

    messages = [{"role": "system", "content": system_prompt}]
    for m in history[-6:]:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})

    resp = client.chat.completions.create(
        model=OPENAI_MODEL, messages=messages, tools=tools, tool_choice="required",
    )
    assistant_msg = resp.choices[0].message

    if not assistant_msg.tool_calls:
        return assistant_msg.content or "No action was needed for this request."

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
    return summary_resp.choices[0].message.content


# --- 4. Data (Snowflake + Cortex AI) --------------------------------------

def _do_snowflake_query(message: str, user: User, db: Session) -> str:
    client = get_openai_client()
    conn = get_snowflake_connection()
    if not client:
        return "OpenAI not configured."
    if not conn:
        return "Snowflake not configured. Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in .env."

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
    operation = classify_resp.choices[0].message.content.strip().upper()
    logger.info(f"[snowflake] classified as: {operation}")

    try:
        cur = conn.cursor()

        if "SENTIMENT" in operation:
            text = _extract_text_for_cortex(client, message, "sentiment analysis")
            sql = f"SELECT SNOWFLAKE.CORTEX.SENTIMENT('{_escape_sql(text)}')"
            cur.execute(sql)
            score = cur.fetchone()[0]
            cur.close()
            sentiment = "positive" if float(score) > 0.1 else "negative" if float(score) < -0.1 else "neutral"
            return (
                f"**Sentiment Analysis**\n\n"
                f"Text: \"{text[:200]}{'...' if len(text) > 200 else ''}\"\n\n"
                f"Score: `{score}` ({sentiment})\n\n"
                f"_Scale: -1.0 (very negative) to +1.0 (very positive)_"
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
            parsed = _safe_json(extract_resp.choices[0].message.content)
            text = parsed.get("text", message)
            lang = parsed.get("target_lang", "en")
            sql = f"SELECT SNOWFLAKE.CORTEX.TRANSLATE('{_escape_sql(text)}', '', '{lang}')"
            cur.execute(sql)
            translated = cur.fetchone()[0]
            cur.close()
            return (
                f"**Translation** (-> {lang})\n\n"
                f"Original: \"{text[:300]}\"\n\n"
                f"Translated: \"{translated}\""
            )

        elif "SUMMARIZE" in operation:
            text = _extract_text_for_cortex(client, message, "summarization")
            sql = f"SELECT SNOWFLAKE.CORTEX.SUMMARIZE('{_escape_sql(text)}')"
            cur.execute(sql)
            summary = cur.fetchone()[0]
            cur.close()
            return f"**Summary**\n\n{summary}"

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
                    )},
                    {"role": "user", "content": message},
                ],
            )
            sql = sql_resp.choices[0].message.content.strip().strip("`").strip()
            logger.info(f"[snowflake] executing SQL: {sql[:200]}")
            cur.execute(sql)
            rows = cur.fetchmany(50)
            cols = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            if not rows:
                return f"Query returned no results.\n\n`{sql}`"
            header = " | ".join(cols)
            lines = [header, "-" * len(header)]
            for row in rows:
                lines.append(" | ".join(str(v) for v in row))
            table = "\n".join(lines)
            return f"```\n{table}\n```\n\nSQL: `{sql}`"

    except Exception as e:
        return f"Snowflake error: {e}"


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


# --- 5. Pay (Skyfire) -----------------------------------------------------

def _do_skyfire_payment(message: str, user: User, db: Session) -> str:
    if not SKYFIRE_API_KEY:
        return "Skyfire not configured. Set SKYFIRE_API_KEY in .env."
    client = get_openai_client()
    if not client:
        return "OpenAI not configured."

    classify_resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": (
                "You are a payment classifier. Given the user's message, decide "
                "which Skyfire operation to perform. Respond with ONLY one label:\n"
                "  BALANCE   - check wallet or balance\n"
                "  LLM_PROXY - use Skyfire's AI proxy to answer a question (pay-per-query)\n"
                "  TOKEN     - create a payment token or session\n"
                "  PAY       - send a payment or transfer funds\n"
                "  INFO      - explain Skyfire or its capabilities\n"
                "Respond with JUST the label."
            )},
            {"role": "user", "content": message},
        ],
    )
    operation = classify_resp.choices[0].message.content.strip().upper()
    logger.info(f"[skyfire] classified as: {operation}")

    sf_headers = {"skyfire-api-key": SKYFIRE_API_KEY, "Content-Type": "application/json"}

    try:
        if "BALANCE" in operation:
            health_resp = requests.get(f"{SKYFIRE_BASE_URL}/v1/health", headers=sf_headers, timeout=10)
            tokens_resp = requests.get(f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers, timeout=10)
            health = health_resp.json() if health_resp.ok else {"error": health_resp.status_code}
            tokens = tokens_resp.json() if tokens_resp.ok else {"error": tokens_resp.status_code}
            token_list = tokens.get("data", [])
            return (
                f"**Skyfire Account Status**\n\n"
                f"Health: {'Connected' if health.get('ok') else 'Error'}\n"
                f"Active Tokens: {len(token_list)}\n\n"
                + ("```json\n" + json.dumps(token_list[:5], indent=2, default=str) + "\n```"
                   if token_list else "_No active payment tokens._")
            )

        elif "LLM_PROXY" in operation:
            token_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json={"type": "pay", "tokenAmount": "0.01", "sellerDomainOrUrl": "https://openrouter.ai"},
                timeout=10,
            )
            proxy_headers = dict(sf_headers)
            if token_resp.ok:
                token_data = token_resp.json().get("data", {})
                token_id = token_data.get("token") or token_data.get("id", "")
                if token_id:
                    proxy_headers["Authorization"] = f"Bearer {token_id}"
            proxy_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/proxy/openrouter/v1/chat/completions",
                headers=proxy_headers,
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant powered by Skyfire's pay-per-query network."},
                        {"role": "user", "content": message},
                    ],
                    "max_tokens": 1000,
                },
                timeout=30,
            )
            if proxy_resp.ok:
                data = proxy_resp.json()
                answer = data.get("choices", [{}])[0].get("message", {}).get("content", "No response")
                usage = data.get("usage", {})
                payment_info = f"\n\n_Tokens used: {usage.get('total_tokens', 'N/A')} | Paid via Skyfire_" if usage else ""
                return f"**Skyfire AI Response**\n\n{answer}{payment_info}"

            fallback = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant. Answer concisely."},
                    {"role": "user", "content": message},
                ],
            )
            return (
                f"**Skyfire AI Response** _(via OpenAI fallback)_\n\n{fallback.choices[0].message.content}\n\n"
                f"_Note: Skyfire LLM proxy requires funded wallet. Response served via direct OpenAI as fallback._"
            )

        elif "TOKEN" in operation:
            token_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json={"type": "pay", "tokenAmount": "0.10", "sellerDomainOrUrl": "https://openrouter.ai"},
                timeout=10,
            )
            if token_resp.ok:
                return f"**Skyfire Token Created**\n\n```json\n{json.dumps(token_resp.json(), indent=2, default=str)}\n```"
            return (
                f"**Skyfire Token Request**\n\nType: `pay`\nAmount: `0.10 USDC`\nSeller: `openrouter.ai`\n\n"
                f"Status: {token_resp.status_code} -- {token_resp.json().get('message', token_resp.text[:200])}\n\n"
                f"_Token creation requires a funded Skyfire wallet. Visit [skyfire.xyz](https://skyfire.xyz) to add funds._"
            )

        elif "PAY" in operation:
            parse_resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": (
                        "Extract payment details from the user's message. "
                        "Return JSON: {\"amount\": number, \"currency\": \"USD\", "
                        "\"recipient\": \"string\", \"description\": \"string\"}. "
                        "Use null for unclear fields."
                    )},
                    {"role": "user", "content": message},
                ],
            )
            pay_intent = _safe_json(parse_resp.choices[0].message.content)
            pay_resp = requests.post(
                f"{SKYFIRE_BASE_URL}/api/v1/tokens", headers=sf_headers,
                json={
                    "type": "pay",
                    "tokenAmount": str(pay_intent.get("amount", "1.00")),
                    "sellerDomainOrUrl": pay_intent.get("recipient", "https://example.com"),
                },
                timeout=15,
            )
            if pay_resp.ok:
                return f"**Payment Token Created**\n\n{json.dumps(pay_resp.json(), indent=2, default=str)}"
            return (
                f"**Payment Intent**\n\n"
                f"Amount: **{pay_intent.get('amount', 'N/A')} {pay_intent.get('currency', 'USD')}**\n"
                f"Recipient: {pay_intent.get('recipient', 'N/A')}\n"
                f"Description: {pay_intent.get('description', 'N/A')}\n\n"
                f"_Payment processed through Skyfire's token protocol. "
                f"Full transaction requires wallet funding at [skyfire.xyz](https://skyfire.xyz)._"
            )

        else:
            health_resp = requests.get(f"{SKYFIRE_BASE_URL}/v1/health", headers=sf_headers, timeout=5)
            status = "Connected" if health_resp.ok and health_resp.json().get("ok") else "Unavailable"
            return (
                f"**Skyfire** -- AI-Native Payment Protocol\n\nStatus: **{status}**\n\n"
                f"Skyfire enables:\n"
                f"- **Pay-per-query AI**: Route LLM calls through Skyfire's proxy\n"
                f"- **Payment tokens**: Programmable payment sessions (`kya`, `pay`, `kya+pay`)\n"
                f"- **Agent payments**: AI agents transact autonomously within set limits\n"
                f"- **Escrow & settlement**: USDC-based micro-payments\n\n"
                f"Try: \"Check my Skyfire balance\", \"Ask Skyfire AI: ...\", \"Create a payment token\""
            )

    except requests.exceptions.Timeout:
        return "Skyfire request timed out. The service may be temporarily unavailable."
    except Exception as e:
        return f"Skyfire error: {e}"


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
    handlers = {"chat": _do_chat, "crew": _do_crew, "action": _do_composio_action, "data": _do_snowflake_query, "pay": _do_skyfire_payment}
    handler = handlers.get(body.mode, _do_chat)
    try:
        reply = handler(body.message, user, db)
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
# Tools status + Health
# ---------------------------------------------------------------------------

@app.get("/api/tools/status")
def tools_status(user: User = Depends(get_current_user)):
    return {
        "crewai":    {"active": True, "label": "CrewAI", "description": "Multi-agent orchestration"},
        "composio":  {"active": get_composio_client() is not None, "label": "Composio", "description": "Gmail, Docs, Drive"},
        "snowflake": {"active": get_snowflake_connection() is not None, "label": "Snowflake", "description": "Cortex AI (NLP)"},
        "skyfire":   {"active": SKYFIRE_API_KEY is not None, "label": "Skyfire", "description": "AI payments"},
        "openai":    {"active": get_openai_client() is not None, "label": "OpenAI", "description": f"LLM ({OPENAI_MODEL})"},
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "orq"}
