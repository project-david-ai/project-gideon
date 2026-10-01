import pytest

from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobMatchType,
)
from project_gideon.repositories.job_ingestion_memory import (
    InMemoryJobIngestionRepository,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


def make_job(
    *,
    job_id: str,
    source: str = "linkedin",
    source_job_id: str | None = None,
    title: str = "Senior Network Engineer",
    company: str = "Acme",
    location: str = "Berlin",
    remote: bool | None = False,
    employment_type: str | None = "full time",
):
    return Job(
        id=job_id,
        tenant_id="tenant-1",
        source=source,
        source_job_id=source_job_id,
        source_url=f"https://example.com/{job_id}",
        title=title,
        company=company,
        description="Role description.",
        location=location,
        remote=remote,
        employment_type=employment_type,
    )


@pytest.mark.asyncio
async def test_distinct_job_is_created():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    result = await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-1",
                source_job_id="source-1",
            )
        )
    )

    assert result.created is True
    assert result.match_type is JobMatchType.DISTINCT
    assert result.job.id == "job-1"

    stored = await repository.list_for_tenant(
        "tenant-1"
    )

    assert len(stored) == 1


@pytest.mark.asyncio
async def test_exact_source_match_returns_existing_canonical_job():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    first = await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-1",
                source="linkedin",
                source_job_id="source-1",
            )
        )
    )

    second = await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-2",
                source="LINKEDIN",
                source_job_id="SOURCE-1",
            )
        )
    )

    assert first.created is True
    assert second.created is False

    assert (
        second.match_type
        is JobMatchType.EXACT_SOURCE_MATCH
    )

    assert second.job.id == "job-1"


@pytest.mark.asyncio
async def test_requisition_match_deduplicates_across_sources():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-1",
                source="linkedin",
                source_job_id="linkedin-1",
            ),
            requisition_id="REQ-77",
        )
    )

    result = await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-2",
                source="company-careers",
                source_job_id="company-9",
            ),
            requisition_id="req-77",
        )
    )

    assert result.created is False

    assert (
        result.match_type
        is JobMatchType.REQUISITION_MATCH
    )

    assert result.job.id == "job-1"


@pytest.mark.asyncio
async def test_strong_canonical_match_deduplicates_cross_source():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-1",
                source="linkedin",
                source_job_id="linkedin-1",
            )
        )
    )

    result = await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-2",
                source="indeed",
                source_job_id="indeed-9",
            )
        )
    )

    assert result.created is False

    assert (
        result.match_type
        is JobMatchType.CANONICAL_STRONG_MATCH
    )

    assert result.job.id == "job-1"


@pytest.mark.asyncio
async def test_tenant_boundaries_prevent_cross_tenant_deduplication():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    first_job = make_job(
        job_id="job-1",
        source_job_id="source-1",
    )

    await service.ingest(
        JobIngestionCandidate(
            job=first_job
        )
    )

    second_job = make_job(
        job_id="job-2",
        source_job_id="source-1",
    ).model_copy(
        update={
            "tenant_id": "tenant-2",
        }
    )

    result = await service.ingest(
        JobIngestionCandidate(
            job=second_job
        )
    )

    assert result.created is True
    assert result.match_type is JobMatchType.DISTINCT


@pytest.mark.asyncio
async def test_identity_precedence_is_source_then_requisition_then_fingerprint():
    repository = InMemoryJobIngestionRepository()

    service = JobIngestionService(
        repository
    )

    await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-source",
                source="linkedin",
                source_job_id="source-1",
                title="Role A",
            ),
            requisition_id="req-a",
        )
    )

    await service.ingest(
        JobIngestionCandidate(
            job=make_job(
                job_id="job-requisition",
                source="company",
                source_job_id="company-2",
                title="Role B",
            ),
            requisition_id="req-b",
        )
    )

    candidate = make_job(
        job_id="incoming",
        source="linkedin",
        source_job_id="source-1",
        title="Role B",
    )

    result = await service.ingest(
        JobIngestionCandidate(
            job=candidate,
            requisition_id="req-b",
        )
    )

    assert (
        result.match_type
        is JobMatchType.EXACT_SOURCE_MATCH
    )

    assert result.job.id == "job-source"
