from __future__ import annotations

from project_gideon.models.delegation import (
    JobsDelegationRequest,
    JobsDelegationResult,
    ResearchDelegationRequest,
    ResearchDelegationResult,
)
from project_gideon.ports.delegation import (
    JobsDelegationPort,
    ResearchDelegationPort,
)


class ResearchDelegationService:
    """
    Gideon's deterministic mediation boundary for research work.

    The career supervisor delegates a bounded objective through this service.
    It does not directly control or impersonate research workers.
    """

    def __init__(
        self,
        port: ResearchDelegationPort,
    ) -> None:
        self._port = port

    async def delegate(
        self,
        request: ResearchDelegationRequest,
    ) -> ResearchDelegationResult:
        return await self._port.delegate_research(
            request
        )


class JobsDelegationService:
    """
    Gideon's deterministic mediation boundary for job-domain work.

    Kept intentionally separate from research delegation because this faction
    may create or reconcile canonical durable job records.
    """

    def __init__(
        self,
        port: JobsDelegationPort,
    ) -> None:
        self._port = port

    async def delegate(
        self,
        request: JobsDelegationRequest,
    ) -> JobsDelegationResult:
        return await self._port.delegate_jobs(
            request
        )