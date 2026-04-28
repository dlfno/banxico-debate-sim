from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(64))
    stance: Mapped[str] = mapped_column(String(32))
    avatar: Mapped[str] = mapped_column(String(8), default="")
    system_prompt: Mapped[str] = mapped_column(Text)


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(512))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decision_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    minutes_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    votes: Mapped[list["Vote"]] = relationship("Vote", backref="meeting", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(
        "Message", backref="meeting", cascade="all, delete-orphan", foreign_keys="Message.meeting_id"
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True, index=True)
    chat_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chat_sessions.id"), nullable=True, index=True)
    agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))  # user | assistant | system | tool | moderator
    phase: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # opening | debate | vote | minutes
    content: Mapped[str] = mapped_column(Text)
    tool_calls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Vote(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), index=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    decision_bps: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text, default="")


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # fact | stance | meeting_summary
    content: Mapped[str] = mapped_column(Text)
    source_meeting_id: Mapped[Optional[int]] = mapped_column(ForeignKey("meetings.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
