from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class PresentationEventType(str, Enum):
    PHASE = "phase"
    ACTIVITY = "activity"
    SOURCE = "source"
    ARTIFACT = "artifact"
    ATTENTION = "attention"
    FINAL = "final"


class PresentationState(str, Enum):
    INFO = "info"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class GideonPresentationEvent(BaseModel):
    """
    Frontend-portable semantic activity emitted by Gideon.

    This contract intentionally hides Project David transport details and
    internal reasoning. CLI, Electron, web, mobile, or Q can consume the same
    event shape.
    """

    type: PresentationEventType

    state: PresentationState = PresentationState.INFO

    phase: str | None = None
    faction: str | None = None

    title: str
    detail: str | None = None

    run_id: str | None = None
    tool: str | None = None
    assistant_id: str | None = None

    source_url: str | None = None

    created_at: datetime = Field(
        default_factory=utc_now
    )

    meta_data: dict[str, Any] = Field(
        default_factory=dict
    )
