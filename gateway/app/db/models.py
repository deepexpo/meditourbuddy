import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("tier in ('free', 'premium')", name="ck_users_tier"),
        CheckConstraint("role in ('user', 'admin', 'support')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    # Default tier for new signups; upgraded manually via SQL (no payment
    # system yet). Carried into the JWT at login/register — see auth.py.
    tier: Mapped[str] = mapped_column(String, nullable=False, default="free")
    # Independent of tier — an admin still has their own free/premium tier.
    # 'support' is reserved for future use: stored, valid, but no endpoint
    # treats it differently from 'user' yet.
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    # Set once at registration — the client shows a consent screen
    # ("informational only, not a medical service provider") and the
    # backend records that the user actually agreed. Never changed after.
    consent_accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Set to now() on logout. Any token with an `iat` before this instant is
    # rejected — a single logout invalidates every session/device at once.
    sessions_invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    __table_args__ = (
        Index("ix_password_reset_codes_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateway.users.id", ondelete="CASCADE"), nullable=False
    )
    # Only the hash is stored — same reasoning as User.password_hash.
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Set once the code is successfully used, or once attempt_count hits
    # settings.password_reset_max_attempts — either way the code is burned.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint(
            "status in ('running', 'complete', 'failed')", name="ck_cases_status"
        ),
        Index("ix_cases_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("gateway.users.id", ondelete="CASCADE"), nullable=False
    )
    intake: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    failure_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    report: Mapped["Report | None"] = relationship(
        back_populates="case", uselist=False, cascade="all, delete-orphan"
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("gateway.cases.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    report: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Nullable: the free-tier basic_pipeline never populates a trace.
    trace: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    input_tokens: Mapped[int] = mapped_column(nullable=False)
    output_tokens: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    case: Mapped[Case] = relationship(back_populates="report")
