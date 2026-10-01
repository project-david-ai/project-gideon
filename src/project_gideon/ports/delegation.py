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

    The public Project David consumer-tool interface is synchronous:
    ToolCallRequestEvent.execute(handler).

    Implementations therefore expose a synchronous boundary rather than
    creating a hidden event loop inside a tool handler.
    """

    def delegate_research(
        self,
        request: ResearchDelegationRequest,
    ) -> ResearchDelegationResult:
        ...


class JobsDelegationPort(Protocol):
    """
    Cross-faction boundary into Gideon's job acquisition/ingestion faction.

    Kept separate from research because this faction has different authority,
    failure semantics and durable-state consequences.
    """

    def delegate_jobs(
        self,
        request: JobsDelegationRequest,
    ) -> JobsDelegationResult:
        ...