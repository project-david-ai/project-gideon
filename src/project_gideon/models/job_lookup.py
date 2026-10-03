from __future__ import annotations

from pydantic import BaseModel


class JobLookupRequest(BaseModel):
    """Read one authoritative canonical job for supervisor reasoning."""

    tenant_id: str
    job_id: str


class JobLookupResult(BaseModel):
    """Canonical job returned through Gideon's read-only supervisor boundary."""

    job: "Job"


from project_gideon.models.job import Job

JobLookupResult.model_rebuild()
