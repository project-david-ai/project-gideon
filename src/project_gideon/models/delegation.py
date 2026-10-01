from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class DelegationStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ResearchSource(BaseModel):
    """
    Provenance returned by the research faction.

    Gideon treats research output as knowledge, not authoritative domain
    mutation. Sources therefore travel with the returned report.
    """

    title: str | None = None
    url: str | None = None
    citation: str | None = None
    meta_data: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def require_provenance(
        self,
    ) -> "ResearchSource":
        if not any(
            (
                self.title,
                self.url,
                self.citation,
                self.meta_data,
            )
        ):
            raise ValueError(
                "ResearchSource requires at least one provenance field."
            )

        return self


class ResearchDelegationRequest(BaseModel):
    """
    Typed boundary from Gideon's career faction to the research faction.

    This is a bounded research objective, not permission for the caller to
    become a research supervisor.
    """

    tenant_id: str
    objective: str

    context: dict[str, Any] = Field(
        default_factory=dict
    )

    max_depth: int | None = Field(
        default=None,
        ge=1,
    )

    requested_at: datetime = Field(
        default_factory=utc_now
    )


class ResearchDelegationResult(BaseModel):
    """
    Knowledge returned by the research faction.

    No canonical Gideon entity is mutated by this contract.
    """

    status: DelegationStatus

    report: str | None = None

    sources: list[ResearchSource] = Field(
        default_factory=list
    )

    research_run_id: str | None = None
    thread_id: str | None = None

    started_at: datetime | None = None
    completed_at: datetime = Field(
        default_factory=utc_now
    )

    error: str | None = None

    meta_data: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_outcome(
        self,
    ) -> "ResearchDelegationResult":
        if self.status is DelegationStatus.SUCCEEDED:
            if not self.report:
                raise ValueError(
                    "Successful research delegation requires a report."
                )

            if self.error:
                raise ValueError(
                    "Successful research delegation cannot contain an error."
                )

        if self.status is DelegationStatus.FAILED:
            if not self.error:
                raise ValueError(
                    "Failed research delegation requires an error."
                )

        return self


class JobsDelegationAction(str, Enum):
    DISCOVER = "discover"
    INGEST = "ingest"
    REFRESH = "refresh"


class JobsDelegationRequest(BaseModel):
    """
    Typed boundary from Gideon's career faction to the jobs faction.

    Unlike research delegation, this boundary may produce durable canonical
    job-domain state.
    """

    tenant_id: str
    action: JobsDelegationAction

    query: str | None = None
    source: str | None = None

    parameters: dict[str, Any] = Field(
        default_factory=dict
    )

    requested_at: datetime = Field(
        default_factory=utc_now
    )


class JobsDelegationResult(BaseModel):
    """
    Result returned by the jobs faction.

    Canonical entity identifiers are returned rather than embedding arbitrary
    worker output into Gideon's durable state.
    """

    status: DelegationStatus

    job_ids: list[str] = Field(
        default_factory=list
    )

    discovered_count: int = Field(
        default=0,
        ge=0,
    )

    ingested_count: int = Field(
        default=0,
        ge=0,
    )

    duplicate_count: int = Field(
        default=0,
        ge=0,
    )

    started_at: datetime | None = None
    completed_at: datetime = Field(
        default_factory=utc_now
    )

    error: str | None = None

    meta_data: dict[str, Any] = Field(
        default_factory=dict
    )

    @model_validator(mode="after")
    def validate_outcome(
        self,
    ) -> "JobsDelegationResult":
        if self.status is DelegationStatus.SUCCEEDED:
            if self.error:
                raise ValueError(
                    "Successful jobs delegation cannot contain an error."
                )

        if self.status is DelegationStatus.FAILED:
            if not self.error:
                raise ValueError(
                    "Failed jobs delegation requires an error."
                )

        return self