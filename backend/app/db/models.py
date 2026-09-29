import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

JSONType = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ts(**kwargs: Any) -> Any:
    return Field(
        default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False, **kwargs)
    )


def _enum_column(enum_cls: type[StrEnum]) -> Column:
    # VARCHAR storage keeps migrations simple when new values are added later.
    return Column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=16,
            values_callable=lambda e: [m.value for m in e],
        ),
        nullable=False,
    )


class ConnectionType(StrEnum):
    prepaid = "prepaid"
    postpaid = "postpaid"


class AccountStatus(StrEnum):
    active = "active"
    suspended = "suspended"
    expired = "expired"


class BillStatus(StrEnum):
    paid = "paid"
    unpaid = "unpaid"
    overdue = "overdue"


class CallChannel(StrEnum):
    phone = "phone"
    web = "web"


class CallStatus(StrEnum):
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"


class Plan(SQLModel, table=True):
    code: str = Field(primary_key=True, max_length=32)
    name: str
    connection_type: ConnectionType = Field(sa_column=_enum_column(ConnectionType))
    price_inr: int
    validity_days: int
    data_mb: int
    voice_minutes: int
    sms: int
    benefits: str = Field(sa_column=Column(Text, nullable=False))


class Customer(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    phone: str = Field(unique=True, index=True, max_length=20)
    full_name: str
    email: str
    city: str
    plan_code: str = Field(foreign_key="plan.code")
    account_status: AccountStatus = Field(
        default=AccountStatus.active, sa_column=_enum_column(AccountStatus)
    )
    activated_on: date
    bill_cycle_day: int | None = None
    validity_ends_on: date | None = None
    autopay_enabled: bool = False
    created_at: datetime = _ts()


class Bill(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("customer.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    period_start: date
    period_end: date
    due_date: date
    amount_inr: float
    status: BillStatus = Field(sa_column=_enum_column(BillStatus))
    line_items: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONType))
    paid_on: date | None = None


class Usage(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    customer_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("customer.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    period_start: date
    data_used_mb: int
    voice_used_minutes: int
    sms_used: int
    rollover_data_mb: int = 0
    updated_at: datetime = _ts()


class Call(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    conversation_id: str = Field(unique=True, index=True, max_length=128)
    channel: CallChannel = Field(default=CallChannel.web, sa_column=_enum_column(CallChannel))
    status: CallStatus = Field(default=CallStatus.in_progress, sa_column=_enum_column(CallStatus))
    caller_number: str | None = Field(default=None, max_length=20)
    customer_id: uuid.UUID | None = Field(
        default=None, sa_column=Column(ForeignKey("customer.id", ondelete="SET NULL"))
    )
    started_at: datetime = _ts()
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    duration_seconds: int | None = None
    summary: str | None = Field(default=None, sa_column=Column(Text))
    successful: bool | None = None
    transcript: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONType))
    call_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONType))


class CallTurn(SQLModel, table=True):
    __tablename__ = "call_turn"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    call_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("call.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    role: str = Field(max_length=16)
    content: str = Field(default="", sa_column=Column(Text, nullable=False))
    tool_name: str | None = Field(default=None, max_length=64)
    tool_args: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONType))
    sources: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONType))
    latency_ms: int | None = None
    created_at: datetime = _ts()


class KnowledgeDocument(SQLModel, table=True):
    __tablename__ = "knowledge_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str = Field(unique=True, max_length=255)
    title: str
    pages: int = 0
    chunks: int = 0
    status: str = Field(default="pending", max_length=16)
    error: str | None = Field(default=None, sa_column=Column(Text))
    indexed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = _ts()
