
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from project_gideon.models.presentation import (
    GideonPresentationEvent,
    PresentationEventType,
    PresentationState,
)
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
        self._presentation_sink: (
            Callable[
                [GideonPresentationEvent],
                None,
            ]
            | None
        ) = None

    def bind_presentation(
        self,
        *,
        presentation_sink: Callable[
            [GideonPresentationEvent],
            None,
        ]
        | None,
    ) -> None:
        self._presentation_sink = presentation_sink

        bind = getattr(
            self._acquisition,
            "bind_presentation",
            None,
        )

        if callable(
            bind
        ):
            bind(
                presentation_sink=presentation_sink
            )

    def _present(
        self,
        *,
        title: str,
        state: PresentationState = PresentationState.IN_PROGRESS,
        detail: str | None = None,
        meta_data: dict[str, object] | None = None,
    ) -> None:
        if self._presentation_sink is None:
            return

        self._presentation_sink(
            GideonPresentationEvent(
                type=PresentationEventType.ACTIVITY,
                state=state,
                phase="jobs",
                faction="jobs",
                title=title,
                detail=detail,
                meta_data=dict(
                    meta_data or {}
                ),
            )
        )

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
            self._present(
                title="Searching current opportunities",
                detail=(
                    "The jobs faction is checking "
                    "verified employer sources."
                ),
            )

            candidates = self._acquire(
                request
            )

            self._present(
                title=(
                    f"Preparing {len(candidates)} "
                    "opportunity"
                    + (
                        ""
                        if len(candidates) == 1
                        else "ies"
                    )
                    if len(candidates) == 1
                    else (
                        f"Preparing {len(candidates)} "
                        "opportunities"
                    )
                ),
                detail=(
                    "Reconciling discovered roles "
                    "with canonical job records."
                ),
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

            self._present(
                title=(
                    f"{ingested_count} new "
                    "opportunit"
                    + (
                        "y"
                        if ingested_count == 1
                        else "ies"
                    )
                    + " added"
                ),
                state=PresentationState.SUCCESS,
                detail=(
                    f"{duplicate_count} already known."
                    if duplicate_count
                    else None
                ),
                meta_data={
                    "discovered_count": len(
                        candidates
                    ),
                    "ingested_count": (
                        ingested_count
                    ),
                    "duplicate_count": (
                        duplicate_count
                    ),
                },
            )

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
            self._present(
                title=(
                    "Job discovery encountered an error"
                ),
                state=PresentationState.ERROR,
                detail=str(
                    exc
                ),
            )

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
