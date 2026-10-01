from __future__ import annotations

from typing import Dict, Optional, Union

from pydantic import BaseModel, Field

from project_gideon.models.candidate import CandidateProfile


ApplicationAnswer = Union[str, bool, int, float]


class ApplicationPackage(BaseModel):
    """
    Canonical package prepared before browser interaction.

    The application worker consumes this object when populating a live
    application form. It contains only known or deliberately generated values.
    Unknown form questions remain unresolved rather than being guessed.
    """

    application_id: str
    job_id: str
    candidate: CandidateProfile

    application_url: str

    cv_file_id: str
    cover_letter: Optional[str] = None
    cover_letter_file_id: Optional[str] = None

    answers: Dict[str, ApplicationAnswer] = Field(default_factory=dict)

    meta_data: Dict[str, object] = Field(default_factory=dict)
