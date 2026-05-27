import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ModelPolicy(Base):
    __tablename__ = "model_policies"
    __table_args__ = (
        UniqueConstraint("org_id", "scene", name="uq_model_policy_org_scene"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    scene: Mapped[str] = mapped_column(String(40), nullable=False)  # chat | planning | paper_gen | grading
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="mock")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="mock-v1")
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

