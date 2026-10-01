from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ApprovalAction(str, Enum):
    SUBMIT_APPLICATION = "submit_application"
    SEND_MESSAGE = "send_message"
    SCHEDULE_INTERVIEW = "schedule_interview"
    WITHDRAW_APPLICATION = "withdraw_application"


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ApprovalRequest(BaseModel):
    """
    Durable request for explicit user authority to perform an external action.
    """

    id: str
    tenant_id: str

    action: ApprovalAction
    resource_id: str

    state: ApprovalState = ApprovalState.PENDING

    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    requested_by_run_id: Optional[str] = None
    requested_by_assistant_id: Optional[str] = None

    summary: Optional[str] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)


class ApprovalGrant(BaseModel):
    """
    Short-lived authority derived from an approved ApprovalRequest.

    A grant is scoped to one action and one resource and must not be reused
    for unrelated external side effects.
    """

    id: str
    approval_request_id: str
    tenant_id: str

    action: ApprovalAction
    resource_id: str

    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime

    consumed_at: Optional[datetime] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None