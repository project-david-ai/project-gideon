from __future__ import annotations

from typing import Protocol

from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIdentity,
    JobUpsertResult,
)


class JobIngestionRepository(Protocol):
    """
    Authoritative persistence boundary for job ingestion.

    Durable implementations must make this operation atomic. Database
    uniqueness and reconciliation belong behind this contract, not in
    agent reasoning or application-level prechecks.
    """

    async def upsert_job(
        self,
        *,
        identity: JobIdentity,
        candidate: Job,
    ) -> JobUpsertResult:
        ...
