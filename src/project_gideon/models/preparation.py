from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from project_gideon.models.application import (
    JobApplication,
    UnresolvedQuestion,
)
from project_gideon.models.browser import (
    BrowserAction,
    BrowserSnapshot,
)


class ApplicationPreparationResult(BaseModel):
    """
    Result of one deterministic application-form preparation pass.

    This contract describes what Gideon prepared. It does not grant
    authority to submit the application.
    """

    application: JobApplication
    snapshot: BrowserSnapshot

    actions: List[BrowserAction] = Field(default_factory=list)

    unresolved_questions: List[UnresolvedQuestion] = Field(
        default_factory=list
    )