import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class CommunityVisibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class MembershipRole(str, enum.Enum):
    OWNER = "owner"
    MODERATOR = "moderator"
    MEMBER = "member"


class Community(Base):
    """A topic community where members discuss and advance IP research & development.

    Communities are the social layer of Saha: spaces where creators, manufacturers
    and researchers gather around a theme (e.g. biotech, clean energy) to share
    ideas and chat. Any verified member can start one.
    """

    __tablename__ = "communities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_institution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    website_url: Mapped[str | None] = mapped_column(String(1000))
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unverified", server_default="unverified")
    topic: Mapped[str] = mapped_column(String(80), nullable=False)
    visibility: Mapped[CommunityVisibility] = mapped_column(
        SAEnum(CommunityVisibility, name="community_visibility", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=CommunityVisibility.PUBLIC,
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CommunityMembership(Base):
    """Join row: which user belongs to which community, and in what capacity."""

    __tablename__ = "community_memberships"
    __table_args__ = (UniqueConstraint("community_id", "user_id", name="uq_community_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[MembershipRole] = mapped_column(
        SAEnum(MembershipRole, name="membership_role", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=MembershipRole.MEMBER,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CommunityMessage(Base):
    """A chat message posted to a community by one of its members.

    Unlike proposal messages (private, encrypted, contact-blocked), community
    chat is group discussion among members and is stored as plaintext.
    """

    __tablename__ = "community_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    community_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("communities.id", ondelete="CASCADE"), nullable=False
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
