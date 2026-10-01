from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ApplicationState(str, Enum):
    DISCOVERED = "discovered"
    SHORTLISTED = "shortlisted"
    PREPARING = "preparing"
    FORM_IN_PROGRESS = "form_in_progress"
    NEEDS_INPUT = "needs_input"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FAILED = "failed"
    WITHDRAWN = "withdrawn"
    CLOSED = "closed"


class UnresolvedQuestion(BaseModel):
    field_id: Optional[str] = None
    question: str
    reason: str
    required: bool = True
    options: List[str] = Field(default_factory=list)


class JobApplication(BaseModel):
    """
    Durable application workflow state.

    This record remains authoritative independently of any individual agent,
    run, thread, or browser session.
    """

    id: str
    tenant_id: str
    job_id: str
    candidate_id: str

    state: ApplicationState = ApplicationState.DISCOVERED

    browser_session_id: Optional[str] = None

    cv_file_id: Optional[str] = None
    cover_letter_file_id: Optional[str] = None

    unresolved_questions: List[UnresolvedQuestion] = Field(
        default_factory=list,
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)
