"""Create demo accounts and default rooms. Run once before starting the backend.
Usage: python seed.py
"""
import uuid, bcrypt
from datetime import datetime, timezone
from database import SessionLocal, engine, Base
from models import User, UserCredential, Room, RoomMember

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()
now = datetime.now(timezone.utc)

def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

# ── Users ─────────────────────────────────────────────────────────────────
user_ids = []
for name, email in [("Sean", "sean@orq.dev"), ("Yug", "yug@orq.dev")]:
    uid = str(uuid.uuid4())
    user_ids.append(uid)
    db.add(User(id=uid, email=email, name=name, role="Engineering", created_at=now, last_seen_at=now))
    db.add(UserCredential(user_id=uid, password_hash=_hash("pass"), created_at=now))

# ── Rooms ─────────────────────────────────────────────────────────────────
sean_id, yug_id = user_ids[0], user_ids[1]

rooms = [
    {"name": "Orq Team",          "icon": "\U0001f3e2",       "description": "Whole team workspace",               "github_repo": "SeanAminov/Orq", "members": [sean_id, yug_id]},
    {"name": "Sean & Yug",        "icon": "\U0001f465",       "description": "Duo collaboration room",             "github_repo": None,             "members": [sean_id, yug_id]},
    {"name": "Sean's Workspace",  "icon": "\U0001f4a1",       "description": "Sean's personal workspace",          "github_repo": None,             "members": [sean_id]},
    {"name": "Yug's Workspace",   "icon": "\U0001f3af",       "description": "Yug's personal workspace",           "github_repo": None,             "members": [yug_id]},
]

for room_info in rooms:
    room_id = str(uuid.uuid4())
    db.add(Room(
        id=room_id,
        name=room_info["name"],
        icon=room_info["icon"],
        description=room_info["description"],
        github_repo=room_info["github_repo"],
        created_by=sean_id,
        created_at=now,
    ))
    for uid in room_info["members"]:
        db.add(RoomMember(
            id=str(uuid.uuid4()),
            room_id=room_id,
            user_id=uid,
            joined_at=now,
        ))

db.commit()
db.close()

print("seed complete!")
print("  Sean  ->  sean@orq.dev / pass")
print("  Yug   ->  yug@orq.dev  / pass")
print(f"  Rooms -> {', '.join(r['name'] for r in rooms)}")
