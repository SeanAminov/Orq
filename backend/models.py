from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow)
    credentials = relationship("UserCredential", back_populates="user", uselist=False)


class UserCredential(Base):
    __tablename__ = "user_credentials"
    user_id = Column(String, ForeignKey("users.id"), primary_key=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="credentials")


class Room(Base):
    __tablename__ = "rooms"
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    icon = Column(String, default="\U0001f4ac")
    description = Column(Text, default="")
    created_by = Column(String, ForeignKey("users.id"), nullable=True)
    github_repo = Column(String, nullable=True)
    skyfire_budget = Column(String, default="0.00")
    created_at = Column(DateTime, default=datetime.utcnow)


class RoomMember(Base):
    __tablename__ = "room_members"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    joined_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    sender_id = Column(String, nullable=False)
    sender_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    run_id = Column(String, ForeignKey("agent_runs.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id = Column(String, primary_key=True, index=True)
    room_id = Column(String, ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    user_name = Column(String, nullable=False)
    intent = Column(String, nullable=False)
    status = Column(String, default="running")
    input_text = Column(Text, default="")
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)


class Activity(Base):
    __tablename__ = "activities"
    id = Column(String, primary_key=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    user_name = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
