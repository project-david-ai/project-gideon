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
    Deterministic mediation boundary for research work.

    The career supervisor delegates a bounded objective through this service.
    It does not control or impersonate research workers.
    """

    def __init__(
        self,
        port: ResearchDelegationPort,
    ) -> None:
        self._port = port

    def delegate(
        self,
        request: ResearchDelegationRequest,
    ) -> ResearchDelegationResult:
        return self._port.delegate_research(
            request
        )


class JobsDelegationService:
    """
    Deterministic mediation boundary for job-domain work.

    This faction remains separate because it may create or reconcile
    authoritative durable job records.
    """

    def __init__(
        self,
        port: JobsDelegationPort,
    ) -> None:
        self._port = port

    def delegate(
        self,
        request: JobsDelegationRequest,
    ) -> JobsDelegationResult:
        return self._port.delegate_jobs(
            request
        )