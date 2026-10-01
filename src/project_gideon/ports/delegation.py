from __future__ import annotations

from typing import Protocol

from project_gideon.models.delegation import (
    JobsDelegationRequest,
    JobsDelegationResult,
    ResearchDelegationRequest,
    ResearchDelegationResult,
)


class ResearchDelegationPort(Protocol):
    """
    Cross-faction boundary into Project David's research orchestration.

    Implementations may use Project David consumer-handled tools, but Gideon's
    domain layer does not depend on that transport.
    """

    async def delegate_research(
        self,
        request: ResearchDelegationRequest,
    ) -> ResearchDelegationResult:
        ...


class JobsDelegationPort(Protocol):
    """
    Cross-faction boundary into Gideon's job acquisition/ingestion faction.

    This remains separate from research because it has different authority,
    failure semantics and durable-state consequences.
    """

    async def delegate_jobs(
        self,
        request: JobsDelegationRequest,
    ) -> JobsDelegationResult:
        ...