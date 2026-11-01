import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class OpenResourceType(str, enum.Enum):
    PATENT = "patent"
    RESEARCH_PAPER = "research_paper"
    TRADEMARK = "trademark"


class OpenResourceStatus(str, enum.Enum):
    PENDING = "pending"      # member-submitted, awaiting admin review
    APPROVED = "approved"    # publicly visible
    REJECTED = "rejected"    # declined by an admin (submitter is notified)


class OpenResource(Base):
    """Open Innovation Library entry: an admin-curated open-source patent,
    research paper, or genericized/abandoned trademark members can freely build
    on (expired/public-domain patents, openly licensed papers, marks now free to
    use). Curation is admin-only; browsing is open.
    """

    __tablename__ = "open_resources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_type: Mapped[OpenResourceType] = mapped_column(
        SAEnum(OpenResourceType, name="open_resource_type", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    authors: Mapped[str | None] = mapped_column(String(500))
    organization: Mapped[str | None] = mapped_column(String(255))
    identifier: Mapped[str | None] = mapped_column(String(120))  # patent number or DOI
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    rights_evidence_url: Mapped[str | None] = mapped_column(String(1000))
    rights_note: Mapped[str | None] = mapped_column(Text)
    jurisdiction: Mapped[str | None] = mapped_column(String(120))
    license: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), server_default="{}", nullable=False)
    published_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[OpenResourceStatus] = mapped_column(
        SAEnum(OpenResourceStatus, name="open_resource_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=OpenResourceStatus.APPROVED,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OpenResourceBuild(Base):
    """A member's public 'I'm building this' declaration on a library resource."""

    __tablename__ = "open_resource_builds"
    __table_args__ = (UniqueConstraint("resource_id", "user_id", name="uq_build_resource_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resource_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("open_resources.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
