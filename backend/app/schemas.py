from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentOut(BaseModel):
    id: int
    slug: str
    display_name: str
    role: str
    stance: str
    avatar: str

    class Config:
        from_attributes = True


class MemoryItemOut(BaseModel):
    id: int
    kind: str
    content: str
    source_meeting_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSessionCreate(BaseModel):
    agent_id: int


class ChatSessionOut(BaseModel):
    id: int
    agent_id: int
    started_at: datetime

    class Config:
        from_attributes = True


class MeetingCreate(BaseModel):
    topic: str = Field(min_length=3)
    agent_ids: Optional[list[int]] = None
    rounds: int = Field(default=2, ge=1, le=4)


class VoteOut(BaseModel):
    agent_id: int
    decision_bps: int
    rationale: str

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    agent_id: Optional[int]
    role: str
    phase: Optional[str]
    content: str
    tool_calls_json: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class MeetingOut(BaseModel):
    id: int
    topic: str
    started_at: datetime
    ended_at: Optional[datetime]
    decision_bps: Optional[int]
    minutes_md: Optional[str]
    votes: list[VoteOut] = []
    messages: list[MessageOut] = []

    class Config:
        from_attributes = True


class MeetingSummary(BaseModel):
    id: int
    topic: str
    started_at: datetime
    ended_at: Optional[datetime]
    decision_bps: Optional[int]

    class Config:
        from_attributes = True
