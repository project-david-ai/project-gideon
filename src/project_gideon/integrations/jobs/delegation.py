
from __future__ import annotations

from datetime import datetime, timezone

from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationRequest,
    JobsDelegationResult,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)
from project_gideon.ports.job_acquisition import (
    JobAcquisitionPort,
)
from project_gideon.ports.job_ingestion_executor import (
    JobIngestionExecutor,
)


class GideonJobsDelegationPort:
    """
    Concrete jobs-faction implementation of JobsDelegationPort.

    Acquisition integrations produce normalised candidates.
    The authoritative ingestion layer decides canonical identity and durable
    job state.
    """

    def __init__(
        self,
        *,
        acquisition: JobAcquisitionPort,
        ingestion: JobIngestionExecutor,
    ) -> None:
        self._acquisition = acquisition
        self._ingestion = ingestion

    def _acquire(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        if request.action is JobsDelegationAction.DISCOVER:
            return self._acquisition.discover(
                request
            )

        if request.action is JobsDelegationAction.INGEST:
            return self._acquisition.ingest(
                request
            )

        if request.action is JobsDelegationAction.REFRESH:
            return self._acquisition.refresh(
                request
            )

        raise ValueError(
            f"Unsupported jobs delegation action: {request.action!r}"
        )

    def delegate_jobs(
        self,
        request: JobsDelegationRequest,
    ) -> JobsDelegationResult:
        started_at = datetime.now(
            timezone.utc
        )

        try:
            candidates = self._acquire(
                request
            )

            job_ids: list[str] = []
            ingested_count = 0
            duplicate_count = 0

            for candidate in candidates:
                if (
                    candidate.job.tenant_id
                    != request.tenant_id
                ):
                    raise ValueError(
                        "Acquisition candidate tenant does not match "
                        "jobs delegation tenant."
                    )

                result = self._ingestion.ingest(
                    candidate
                )

                if result.job.id not in job_ids:
                    job_ids.append(
                        result.job.id
                    )

                if result.created:
                    ingested_count += 1
                else:
                    duplicate_count += 1

            return JobsDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                job_ids=job_ids,
                discovered_count=len(
                    candidates
                ),
                ingested_count=ingested_count,
                duplicate_count=duplicate_count,
                started_at=started_at,
                completed_at=datetime.now(
                    timezone.utc
                ),
                meta_data={
                    "action": request.action.value,
                    "source": request.source,
                },
            )

        except Exception as exc:
            return JobsDelegationResult(
                status=DelegationStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now(
                    timezone.utc
                ),
                error=str(
                    exc
                ),
                meta_data={
                    "action": request.action.value,
                    "source": request.source,
                },
            )
