
from __future__ import annotations

from typing import Protocol

from project_gideon.models.delegation import (
    JobsDelegationRequest,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)


class JobAcquisitionPort(Protocol):
    """
    External job-acquisition boundary used by Gideon's jobs faction.

    Implementations may use an MCP server, API, feed, browser-backed source,
    or another integration mechanism.

    They return normalised candidates only. They do not own canonical Gideon
    job persistence.
    """

    def discover(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        ...

    def ingest(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        ...

    def refresh(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        ...
