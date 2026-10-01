from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class JobCompensation(BaseModel):
    currency: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    period: Optional[str] = None
    raw_text: Optional[str] = None


class Job(BaseModel):
    """
    Canonical representation of a discovered job.

    Source-specific job-board or ATS payloads should be normalised into this
    model before entering the Gideon domain layer.
    """

    id: str
    tenant_id: str

    source: str
    source_job_id: Optional[str] = None
    source_url: str
    application_url: Optional[str] = None

    title: str
    company: str
    description: str

    location: Optional[str] = None
    remote: Optional[bool] = None
    employment_type: Optional[str] = None

    compensation: Optional[JobCompensation] = None

    requirements: List[str] = Field(default_factory=list)

    published_at: Optional[datetime] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    meta_data: Dict[str, object] = Field(default_factory=dict)
