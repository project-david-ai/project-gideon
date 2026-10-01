
import pytest

from project_gideon.integrations.jobs.async_ingestion import (
    JobIngestionExecutorClosed,
    ThreadedJobIngestionExecutor,
)
from project_gideon.models.job import (
    Job,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)
from project_gideon.repositories.job_ingestion_memory import (
    InMemoryJobIngestionRepository,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


def make_candidate(
    job_id: str,
) -> JobIngestionCandidate:
    return JobIngestionCandidate(
        job=Job(
            id=job_id,
            tenant_id="tenant-1",
            source="test",
            source_job_id=job_id,
            source_url=f"https://example.com/{job_id}",
            title="Engineer",
            company="Acme",
            description="Role.",
        )
    )


def test_executor_runs_async_ingestion_behind_explicit_boundary():
    service = JobIngestionService(
        InMemoryJobIngestionRepository()
    )

    with ThreadedJobIngestionExecutor(
        service
    ) as executor:
        result = executor.ingest(
            make_candidate(
                "job-1"
            )
        )

        assert result.created is True
        assert result.job.id == "job-1"


def test_executor_preserves_authoritative_duplicate_result():
    service = JobIngestionService(
        InMemoryJobIngestionRepository()
    )

    with ThreadedJobIngestionExecutor(
        service
    ) as executor:
        first = executor.ingest(
            make_candidate(
                "job-1"
            )
        )

        second = executor.ingest(
            make_candidate(
                "job-2"
            ).model_copy(
                update={
                    "job": make_candidate(
                        "job-1"
                    ).job.model_copy(
                        update={
                            "id": "job-2",
                        }
                    )
                }
            )
        )

        assert first.created is True
        assert second.created is False
        assert second.job.id == "job-1"


def test_executor_rejects_use_after_close():
    service = JobIngestionService(
        InMemoryJobIngestionRepository()
    )

    executor = ThreadedJobIngestionExecutor(
        service
    )

    executor.close()

    with pytest.raises(
        JobIngestionExecutorClosed,
        match="closed",
    ):
        executor.ingest(
            make_candidate(
                "job-1"
            )
        )


def test_close_is_idempotent():
    service = JobIngestionService(
        InMemoryJobIngestionRepository()
    )

    executor = ThreadedJobIngestionExecutor(
        service
    )

    executor.close()
    executor.close()
