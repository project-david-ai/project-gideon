from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class SupervisorToolCallRecord(BaseModel):
    """
    Auditable record of a Gideon-owned consumer-side function tool call.
    """

    tool_name: str

    arguments: dict[str, Any] = Field(
        default_factory=dict
    )

    action_id: str | None = None
    tool_call_id: str | None = None

    executed: bool = False


class SupervisorTurnResult(BaseModel):
    """
    Typed result of one externally initiated Gideon supervisor turn.
    """

    assistant_id: str
    thread_id: str
    message_id: str
    run_id: str

    content: str

    tool_calls: list[SupervisorToolCallRecord] = Field(
        default_factory=list
    )

    completed_at: datetime = Field(
        default_factory=utc_now
    )

    meta_data: dict[str, Any] = Field(
        default_factory=dict
    )
