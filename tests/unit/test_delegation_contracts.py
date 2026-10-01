from datetime import timezone

import pytest
from pydantic import ValidationError

from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationRequest,
    JobsDelegationResult,
    ResearchDelegationRequest,
    ResearchDelegationResult,
    ResearchSource,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
    ResearchDelegationService,
)


def test_research_request_is_tenant_scoped_and_timezone_aware():
    request = ResearchDelegationRequest(
        tenant_id="tenant-1",
        objective="Research Acme's engineering hiring plans.",
    )

    assert request.tenant_id == "tenant-1"
    assert request.requested_at.tzinfo is timezone.utc


def test_successful_research_requires_report():
    with pytest.raises(
        ValidationError,
        match="requires a report",
    ):
        ResearchDelegationResult(
            status=DelegationStatus.SUCCEEDED,
        )


def test_failed_research_requires_error():
    with pytest.raises(
        ValidationError,
        match="requires an error",
    ):
        ResearchDelegationResult(
            status=DelegationStatus.FAILED,
        )


def test_research_source_requires_provenance():
    with pytest.raises(
        ValidationError,
        match="provenance",
    ):
        ResearchSource()


def test_successful_research_returns_knowledge_and_provenance():
    result = ResearchDelegationResult(
        status=DelegationStatus.SUCCEEDED,
        report="Acme is expanding its platform engineering organisation.",
        sources=[
            ResearchSource(
                url="https://example.com/source",
            )
        ],
        research_run_id="research-1",
        thread_id="thread-1",
    )

    assert result.report
    assert len(result.sources) == 1
    assert result.research_run_id == "research-1"


def test_jobs_request_uses_explicit_domain_action():
    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="senior network engineer",
    )

    assert request.action is JobsDelegationAction.DISCOVER


def test_jobs_result_returns_canonical_ids():
    result = JobsDelegationResult(
        status=DelegationStatus.SUCCEEDED,
        job_ids=[
            "job-1",
            "job-2",
        ],
        discovered_count=3,
        ingested_count=2,
        duplicate_count=1,
    )

    assert result.job_ids == [
        "job-1",
        "job-2",
    ]

    assert result.discovered_count == 3
    assert result.ingested_count == 2
    assert result.duplicate_count == 1


def test_failed_jobs_result_requires_error():
    with pytest.raises(
        ValidationError,
        match="requires an error",
    ):
        JobsDelegationResult(
            status=DelegationStatus.FAILED,
        )


@pytest.mark.asyncio
async def test_research_service_uses_only_research_port():
    calls = []

    class FakeResearchPort:
        async def delegate_research(
            self,
            request,
        ):
            calls.append(request)

            return ResearchDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                report="Research complete.",
            )

    service = ResearchDelegationService(
        FakeResearchPort()
    )

    request = ResearchDelegationRequest(
        tenant_id="tenant-1",
        objective="Research Acme.",
    )

    result = await service.delegate(
        request
    )

    assert calls == [request]
    assert result.report == "Research complete."


@pytest.mark.asyncio
async def test_jobs_service_uses_only_jobs_port():
    calls = []

    class FakeJobsPort:
        async def delegate_jobs(
            self,
            request,
        ):
            calls.append(request)

            return JobsDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                job_ids=["job-1"],
                discovered_count=1,
                ingested_count=1,
            )

    service = JobsDelegationService(
        FakeJobsPort()
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="python engineer",
    )

    result = await service.delegate(
        request
    )

    assert calls == [request]
    assert result.job_ids == ["job-1"]