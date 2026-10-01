from __future__ import annotations

from project_gideon.integrations.jobs.async_ingestion import (
    ThreadedJobIngestionExecutor,
)
from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobMatchType,
)
from project_gideon.repositories.job_ingestion_memory import (
    InMemoryJobIngestionRepository,
)
from project_gideon.services.job_identity import (
    build_job_identity,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


def make_payload(
    *,
    job_id: int,
    title: str = "Abuse Investigator",
    location: str = "Dublin",
    requisition_id: str | None = "See Opening ID",
):
    return {
        "jobs": [
            {
                "id": job_id,
                "title": title,
                "absolute_url": (
                    "https://boards.greenhouse.io/"
                    f"stripe/jobs/{job_id}"
                ),
                "content": "<p>Role description</p>",
                "company_name": "Stripe",
                "requisition_id": requisition_id,
                "location": {
                    "name": location,
                },
                "metadata": None,
            }
        ]
    }


def candidate_from_payload(
    payload,
):
    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: payload
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-live-ats",
        action=JobsDelegationAction.DISCOVER,
        source="greenhouse",
        parameters={
            "boards": [
                {
                    "token": "stripe",
                    "company": "Stripe",
                }
            ]
        },
    )

    return adapter.discover(
        request
    )[0]


def test_greenhouse_placeholder_requisition_is_not_authoritative_identity():
    candidate = candidate_from_payload(
        make_payload(
            job_id=8172487,
        )
    )

    assert (
        candidate.requisition_id
        == "See Opening ID"
    )

    identity = build_job_identity(
        candidate
    )

    assert identity.requisition_id is None


def test_same_source_distinct_native_ids_do_not_collapse_on_fingerprint():
    first = candidate_from_payload(
        make_payload(
            job_id=8172487,
        )
    )

    second = candidate_from_payload(
        make_payload(
            job_id=8172508,
        )
    )

    repository = (
        InMemoryJobIngestionRepository()
    )

    executor = ThreadedJobIngestionExecutor(
        JobIngestionService(
            repository
        )
    )

    try:
        first_result = executor.ingest(
            first
        )

        second_result = executor.ingest(
            second
        )
    finally:
        executor.close()

    assert first_result.created is True
    assert second_result.created is True

    assert (
        first_result.match_type
        == JobMatchType.DISTINCT
    )

    assert (
        second_result.match_type
        == JobMatchType.DISTINCT
    )

    assert (
        first_result.job.id
        != second_result.job.id
    )


def test_unique_cross_source_fingerprint_can_still_reconcile():
    greenhouse = candidate_from_payload(
        make_payload(
            job_id=9001,
            title="Network Engineer",
            location="Berlin",
            requisition_id=None,
        )
    )

    other_job = greenhouse.job.model_copy(
        update={
            "id": "lever:stripe:abc-123",
            "source": "lever",
            "source_job_id": "abc-123",
            "source_url": (
                "https://jobs.lever.co/"
                "stripe/abc-123"
            ),
            "application_url": (
                "https://jobs.lever.co/"
                "stripe/abc-123"
            ),
        }
    )

    other = JobIngestionCandidate(
        job=other_job,
        requisition_id=None,
    )

    repository = (
        InMemoryJobIngestionRepository()
    )

    executor = ThreadedJobIngestionExecutor(
        JobIngestionService(
            repository
        )
    )

    try:
        first_result = executor.ingest(
            greenhouse
        )

        second_result = executor.ingest(
            other
        )
    finally:
        executor.close()

    assert first_result.created is True
    assert second_result.created is False

    assert (
        second_result.match_type
        == JobMatchType.CANONICAL_STRONG_MATCH
    )

    assert (
        second_result.job.id
        == first_result.job.id
    )


def test_ambiguous_fingerprint_stops_cross_source_auto_merge():
    first = candidate_from_payload(
        make_payload(
            job_id=1001,
            title="Abuse Investigator",
            location="Dublin",
            requisition_id=None,
        )
    )

    second = candidate_from_payload(
        make_payload(
            job_id=1002,
            title="Abuse Investigator",
            location="Dublin",
            requisition_id=None,
        )
    )

    cross_source_job = first.job.model_copy(
        update={
            "id": "lever:stripe:cross-source",
            "source": "lever",
            "source_job_id": "cross-source",
            "source_url": (
                "https://jobs.lever.co/"
                "stripe/cross-source"
            ),
            "application_url": (
                "https://jobs.lever.co/"
                "stripe/cross-source"
            ),
        }
    )

    cross_source = JobIngestionCandidate(
        job=cross_source_job,
        requisition_id=None,
    )

    repository = (
        InMemoryJobIngestionRepository()
    )

    executor = ThreadedJobIngestionExecutor(
        JobIngestionService(
            repository
        )
    )

    try:
        first_result = executor.ingest(
            first
        )

        second_result = executor.ingest(
            second
        )

        cross_result = executor.ingest(
            cross_source
        )
    finally:
        executor.close()

    assert first_result.created is True
    assert second_result.created is True
    assert cross_result.created is True

    assert (
        cross_result.match_type
        == JobMatchType.DISTINCT
    )
