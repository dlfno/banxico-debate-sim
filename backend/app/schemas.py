from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AgentDescription(BaseModel):
    tagline: str
    summary: str
    focus: list[str]
    skills: list[str]
    data_sources: list[str]


class AgentOut(BaseModel):
    id: int
    slug: str
    display_name: str
    role: str
    stance: str
    avatar: str
    description: Optional[AgentDescription] = None

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


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str

    class Config:
        from_attributes = True


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    display_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


class AuthOut(BaseModel):
    token: str
    user: UserOut


class ChatSessionCreate(BaseModel):
    agent_id: int


class ChatSessionOut(BaseModel):
    id: int
    agent_id: int
    started_at: datetime
    created_by: UserOut

    class Config:
        from_attributes = True


class ChatSessionSummary(BaseModel):
    id: int
    agent_id: int
    agent_name: str
    agent_avatar: str
    started_at: datetime
    last_message_at: Optional[datetime]
    message_count: int
    created_by: UserOut


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
    created_by: UserOut
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
    created_by: UserOut

    class Config:
        from_attributes = True
