import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from app.api.schemas.community import CommunityResponse
from app.api.schemas.institution import https_url


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    resource_id: uuid.UUID | None = None
    goal: str = Field(min_length=10, max_length=5000)
    repository_url: str | None = Field(default=None, max_length=1000)
    contribution_guide: str | None = Field(default=None, max_length=5000)
    skills_needed: list[str] = Field(default_factory=list, max_length=12)
    _url = field_validator("repository_url")(https_url)

    @field_validator("skills_needed")
    @classmethod
    def clean_skills(cls, values):
        cleaned = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        if any(len(v) > 60 for v in cleaned):
            raise ValueError("Skills must be at most 60 characters")
        return cleaned

    @field_validator("name", "goal")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be blank")
        return value.strip()


class ProjectResponse(BaseModel):
    space: CommunityResponse
    resource_id: uuid.UUID | None = None
    resource_title: str | None
    source_url: str | None
    goal: str
    repository_url: str | None
    contribution_guide: str | None
    skills_needed: list[str]
    stage: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    assigned_to: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    version: int = Field(ge=1)
    status: Literal["todo", "doing", "done"]


class ProjectStageUpdate(BaseModel):
    stage: Literal["idea", "research", "prototype", "testing", "released"]


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    created_by: uuid.UUID
    title: str
    description: str | None
    status: str
    assigned_to: uuid.UUID | None
    version: int
    created_at: datetime
    model_config = {"from_attributes": True}


Platform = Literal["website", "google_drive", "google_docs", "google_sheets", "google_slides", "dropbox", "onedrive", "github", "gitlab", "figma", "notion", "youtube", "zenodo", "osf", "other"]
FileType = Literal["document", "spreadsheet", "presentation", "design", "code", "dataset", "image", "video", "paper", "folder", "other"]


class ReferenceCreate(BaseModel):
    model_config = {"str_strip_whitespace": True, "extra": "forbid"}
    title: str = Field(min_length=1, max_length=180)
    url: str = Field(min_length=8, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)
    platform: Platform = "website"
    file_type: FileType = "document"
    pinned: bool = False
    _url = field_validator("url")(https_url)

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        from urllib.parse import urlsplit
        import ipaddress
        if any(ord(c) < 32 or c in "\\" for c in value):
            raise ValueError("Use a valid public HTTPS link")
        parts = urlsplit(value)
        host = (parts.hostname or "").lower().rstrip(".")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host or host.endswith((".localhost", ".local", ".internal")):
                raise ValueError("Use a public platform hostname")
        else:
            if not address.is_global:
                raise ValueError("Private network addresses are not supported")
        try:
            parts.port
        except ValueError:
            raise ValueError("Invalid URL port") from None
        return value


class ReferenceUpdate(ReferenceCreate):
    version: int = Field(ge=1)


class ReferenceResponse(ReferenceCreate):
    id: uuid.UUID
    project_id: uuid.UUID
    created_by: uuid.UUID
    version: int
    created_at: datetime
    model_config = {"from_attributes": True}
