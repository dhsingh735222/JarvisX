import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Auth ----------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = ""


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Conversations / Messages ----------
class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    tool_calls: dict | list | None = None
    tool_use_id: str | None = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


# ---------- Chat ----------
class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    conversation_id: int
    messages: list[MessageOut]
    pending_action: "PendingActionOut | None" = None


# ---------- Approvals ----------
class PendingActionOut(BaseModel):
    id: int
    conversation_id: int
    tool_name: str
    tool_input: dict
    status: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalDecision(BaseModel):
    approve: bool


# ---------- API Keys / Settings ----------
class ApiKeyIn(BaseModel):
    provider: str
    value: str


class ApiKeyOut(BaseModel):
    provider: str
    configured: bool
    updated_at: datetime.datetime | None = None


class SettingsOut(BaseModel):
    llm_provider: str
    llm_model: str
    tts_engine: str
    api_keys: list[ApiKeyOut]


class SettingsUpdate(BaseModel):
    llm_provider: str | None = None
    llm_model: str | None = None
    tts_engine: str | None = None


# ---------- Activity Log ----------
class ActivityLogOut(BaseModel):
    id: int
    action_type: str
    tool_name: str | None
    input_data: dict | list | None
    output_data: dict | list | str | None
    status: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Memory ----------
class MemoryItemIn(BaseModel):
    category: str = "fact"
    key: str
    value: str


class MemoryItemOut(BaseModel):
    id: int
    category: str
    key: str
    value: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)
