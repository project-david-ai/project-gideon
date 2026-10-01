from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from project_gideon.models.job import Job


class JobMatchType(str, Enum):
    """
    Deterministic duplicate classification.

    Ordering is semantic, not probabilistic:
    exact source identity is strongest, then requisition identity,
    then canonical strong match, then distinct.
    """

    EXACT_SOURCE_MATCH = "exact_source_match"
    REQUISITION_MATCH = "requisition_match"
    CANONICAL_STRONG_MATCH = "canonical_strong_match"
    DISTINCT = "distinct"


class JobIngestionCandidate(BaseModel):
    """
    Normalised candidate presented to the authoritative ingestion service.

    Source adapters must normalise source-specific payloads into Job before
    this boundary. Requisition identity is kept explicit because it can
    provide cross-source duplicate evidence.
    """

    job: Job
    requisition_id: str | None = None


class JobIdentity(BaseModel):
    """
    Deterministic identity material used by repository implementations.
    """

    tenant_id: str
    source: str
    source_job_id: str | None = None
    requisition_id: str | None = None
    canonical_fingerprint: str


class JobUpsertResult(BaseModel):
    """
    Repository-level atomic reconciliation result.
    """

    job: Job
    match_type: JobMatchType
    created: bool


class JobIngestionResult(BaseModel):
    """
    Application-layer result for one candidate ingestion.
    """

    job: Job
    match_type: JobMatchType
    created: bool

    provenance: dict[str, object] = Field(
        default_factory=dict
    )
