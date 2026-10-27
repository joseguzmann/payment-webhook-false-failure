from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.now(timezone.utc)


class Payment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    customer: str
    amount_cents: int
    status: str = "pending"
    link_id: str | None = None
    link_url: str | None = None
    updated_at: datetime = Field(default_factory=now)


class OutboxMessage(SQLModel, table=True):
    """What the customer receives. `channel` is whatsapp or email; `source` is agent or webhook."""

    id: int | None = Field(default=None, primary_key=True)
    customer: str
    channel: str
    text: str
    source: str
    trace_id: str | None = None
    created_at: datetime = Field(default_factory=now)


class Trace(SQLModel, table=True):
    """One agent turn. Stands in for the LLM trace (Langfuse in the original system)."""

    id: str = Field(primary_key=True)
    customer: str
    input: str
    output: str = ""
    created_at: datetime = Field(default_factory=now)
