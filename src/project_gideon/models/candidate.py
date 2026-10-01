from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CandidateIdentity(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None


class WorkAuthorisation(BaseModel):
    country: str
    status: str
    requires_sponsorship: Optional[bool] = None


class CandidatePreferences(BaseModel):
    target_locations: List[str] = Field(default_factory=list)
    remote_allowed: bool = True
    hybrid_allowed: bool = True
    onsite_allowed: bool = False
    willing_to_relocate: Optional[bool] = None
    notice_period: Optional[str] = None
    salary_expectations: Dict[str, str] = Field(default_factory=dict)


class CandidateProfile(BaseModel):
    """
    Canonical tenant-owned candidate profile.

    This model contains reusable, authoritative candidate information.
    Generated application answers and job-specific claims do not belong here.
    """

    id: str
    tenant_id: str
    identity: CandidateIdentity

    headline: Optional[str] = None
    summary: Optional[str] = None

    work_authorisation: List[WorkAuthorisation] = Field(
        default_factory=list,
    )

    preferences: CandidatePreferences = Field(
        default_factory=CandidatePreferences,
    )

    skills: List[str] = Field(default_factory=list)

    default_cv_file_id: Optional[str] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)
