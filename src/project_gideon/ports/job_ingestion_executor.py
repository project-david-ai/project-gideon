
from __future__ import annotations

from typing import Protocol

from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobIngestionResult,
)


class JobIngestionExecutor(Protocol):
    """
    Explicit synchronous bridge into authoritative job ingestion.

    This exists because Project David's consumer-tool handler contract is
    synchronous while Gideon's durable repository/service boundary is async.
    """

    def ingest(
        self,
        candidate: JobIngestionCandidate,
    ) -> JobIngestionResult:
        ...
