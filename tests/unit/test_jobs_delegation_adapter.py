
from project_gideon.integrations.jobs.delegation import (
    GideonJobsDelegationPort,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationRequest,
)
from project_gideon.models.job import (
    Job,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobIngestionResult,
    JobMatchType,
)


def make_candidate(
    job_id: str,
    *,
    tenant_id: str = "tenant-1",
) -> JobIngestionCandidate:
    return JobIngestionCandidate(
        job=Job(
            id=job_id,
            tenant_id=tenant_id,
            source="test-source",
            source_job_id=f"source-{job_id}",
            source_url=f"https://example.com/{job_id}",
            title="Senior Engineer",
            company="Acme",
            description="Role.",
        )
    )


class FakeAcquisition:
    def __init__(
        self,
        candidates,
    ):
        self.candidates = candidates
        self.calls = []

    def discover(
        self,
        request,
    ):
        self.calls.append(
            (
                "discover",
                request,
            )
        )

        return self.candidates

    def ingest(
        self,
        request,
    ):
        self.calls.append(
            (
                "ingest",
                request,
            )
        )

        return self.candidates

    def refresh(
        self,
        request,
    ):
        self.calls.append(
            (
                "refresh",
                request,
            )
        )

        return self.candidates


class FakeIngestion:
    def __init__(
        self,
        *,
        duplicate_ids=None,
    ):
        self.duplicate_ids = set(
            duplicate_ids or []
        )

        self.calls = []

    def ingest(
        self,
        candidate,
    ):
        self.calls.append(
            candidate
        )

        created = (
            candidate.job.id
            not in self.duplicate_ids
        )

        return JobIngestionResult(
            job=candidate.job,
            match_type=(
                JobMatchType.DISTINCT
                if created
                else JobMatchType.EXACT_SOURCE_MATCH
            ),
            created=created,
        )


def test_discover_routes_through_acquisition_then_ingestion():
    candidates = [
        make_candidate(
            "job-1"
        ),
        make_candidate(
            "job-2"
        ),
    ]

    acquisition = FakeAcquisition(
        candidates
    )

    ingestion = FakeIngestion()

    port = GideonJobsDelegationPort(
        acquisition=acquisition,
        ingestion=ingestion,
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="platform engineer",
    )

    result = port.delegate_jobs(
        request
    )

    assert result.status is DelegationStatus.SUCCEEDED

    assert result.job_ids == [
        "job-1",
        "job-2",
    ]

    assert result.discovered_count == 2
    assert result.ingested_count == 2
    assert result.duplicate_count == 0

    assert acquisition.calls == [
        (
            "discover",
            request,
        )
    ]

    assert ingestion.calls == candidates


def test_duplicate_counts_are_derived_from_authoritative_ingestion():
    candidates = [
        make_candidate(
            "job-1"
        ),
        make_candidate(
            "job-2"
        ),
    ]

    port = GideonJobsDelegationPort(
        acquisition=FakeAcquisition(
            candidates
        ),
        ingestion=FakeIngestion(
            duplicate_ids={
                "job-2",
            }
        ),
    )

    result = port.delegate_jobs(
        JobsDelegationRequest(
            tenant_id="tenant-1",
            action=JobsDelegationAction.DISCOVER,
        )
    )

    assert result.discovered_count == 2
    assert result.ingested_count == 1
    assert result.duplicate_count == 1


def test_ingest_action_routes_to_acquisition_ingest():
    acquisition = FakeAcquisition(
        []
    )

    port = GideonJobsDelegationPort(
        acquisition=acquisition,
        ingestion=FakeIngestion(),
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.INGEST,
    )

    result = port.delegate_jobs(
        request
    )

    assert result.status is DelegationStatus.SUCCEEDED

    assert acquisition.calls == [
        (
            "ingest",
            request,
        )
    ]


def test_refresh_action_routes_to_acquisition_refresh():
    acquisition = FakeAcquisition(
        []
    )

    port = GideonJobsDelegationPort(
        acquisition=acquisition,
        ingestion=FakeIngestion(),
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.REFRESH,
    )

    result = port.delegate_jobs(
        request
    )

    assert result.status is DelegationStatus.SUCCEEDED

    assert acquisition.calls == [
        (
            "refresh",
            request,
        )
    ]


def test_tenant_mismatch_fails_without_persisting_candidate():
    ingestion = FakeIngestion()

    port = GideonJobsDelegationPort(
        acquisition=FakeAcquisition(
            [
                make_candidate(
                    "job-1",
                    tenant_id="tenant-other",
                )
            ]
        ),
        ingestion=ingestion,
    )

    result = port.delegate_jobs(
        JobsDelegationRequest(
            tenant_id="tenant-1",
            action=JobsDelegationAction.DISCOVER,
        )
    )

    assert result.status is DelegationStatus.FAILED
    assert "tenant" in result.error.lower()
    assert ingestion.calls == []


def test_acquisition_failure_returns_typed_failed_result():
    class BrokenAcquisition:
        def discover(
            self,
            request,
        ):
            raise RuntimeError(
                "source unavailable"
            )

        def ingest(
            self,
            request,
        ):
            raise AssertionError()

        def refresh(
            self,
            request,
        ):
            raise AssertionError()

    port = GideonJobsDelegationPort(
        acquisition=BrokenAcquisition(),
        ingestion=FakeIngestion(),
    )

    result = port.delegate_jobs(
        JobsDelegationRequest(
            tenant_id="tenant-1",
            action=JobsDelegationAction.DISCOVER,
        )
    )

    assert result.status is DelegationStatus.FAILED
    assert result.error == "source unavailable"
