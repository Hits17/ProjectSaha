import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UserRole(str, enum.Enum):
    CREATOR = "creator"
    MANUFACTURER = "manufacturer"
    LEGAL = "legal"
    ADMIN = "admin"


class KYCStatus(str, enum.Enum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.CREATOR,
    )
    kyc_status: Mapped[KYCStatus] = mapped_column(
        SAEnum(KYCStatus, name="kyc_status", create_type=False,
               values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=KYCStatus.PENDING,
    )
    kyc_inquiry_id: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # --- Account protection (enterprise auth hardening) ---
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # TOTP MFA. Secret is stored encrypted (AES-256-GCM) — see app.core.mfa.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255))
    # Highest TOTP counter already accepted. Codes at or below it are refused,
    # so an intercepted code cannot be replayed within its window (SAHA-030).
    mfa_last_counter: Mapped[int | None] = mapped_column(BigInteger)

    # Profile picture: MinIO object key (avatars/<user_id>/<uuid>.<ext>), served
    # through the authenticated avatar endpoint — never a raw storage URL.
    avatar_key: Mapped[str | None] = mapped_column(String(500))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def has_avatar(self) -> bool:
        """Read by UserResponse (from_attributes) so clients know to fetch the avatar."""
        return self.avatar_key is not None
