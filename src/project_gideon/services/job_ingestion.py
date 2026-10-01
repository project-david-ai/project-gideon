from __future__ import annotations

from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobIngestionResult,
)
from project_gideon.ports.job_ingestion import (
    JobIngestionRepository,
)
from project_gideon.services.job_identity import (
    build_job_identity,
)


class JobIngestionService:
    """
    Deterministic authoritative job-ingestion application service.

    Agents may discover or reason about opportunities, but this service owns
    the transition into canonical Gideon job state.
    """

    def __init__(
        self,
        repository: JobIngestionRepository,
    ) -> None:
        self._repository = repository

    async def ingest(
        self,
        candidate: JobIngestionCandidate,
    ) -> JobIngestionResult:
        identity = build_job_identity(
            candidate
        )

        result = await self._repository.upsert_job(
            identity=identity,
            candidate=candidate.job,
        )

        return JobIngestionResult(
            job=result.job,
            match_type=result.match_type,
            created=result.created,
            provenance={
                "source": candidate.job.source,
                "source_job_id": candidate.job.source_job_id,
                "requisition_id": candidate.requisition_id,
                "canonical_fingerprint": (
                    identity.canonical_fingerprint
                ),
            },
        )
