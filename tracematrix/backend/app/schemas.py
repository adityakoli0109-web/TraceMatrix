from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.ethutil import classify_seed


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str


class InvestigationCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = ""
    seed_value: str
    objective: str = ""
    date_from: datetime | None = None
    date_to: datetime | None = None
    max_depth: int = Field(default=2, ge=1, le=5)
    max_transactions: int = Field(default=100, ge=1, le=500)
    selected_sources: dict[str, bool] = Field(default_factory=lambda: {"github": True, "threat_feeds": True, "chain": True})
    confirm_scope: bool = False

    def seed_type(self) -> str:
        return classify_seed(self.seed_value.strip())


class InvestigationUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    objective: str | None = None


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)


class ReviewCreate(BaseModel):
    decision: str = Field(pattern="^(under_review|confirmed_lead|rejected)$")
    rationale: str = Field(min_length=3)


class SourceCreate(BaseModel):
    name: str
    source_type: str = "threat_feed"
    endpoint: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class PageParams(BaseModel):
    page: int = 1
    page_size: int = 20
    q: str | None = None
    sort: str = "created_at"
    order: str = "desc"
