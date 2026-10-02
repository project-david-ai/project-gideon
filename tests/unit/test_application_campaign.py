import pytest

from project_gideon.models import (
    ApplicationState,
    CandidateIdentity,
    CandidateProfile,
    Job,
    JobApplication,
)
from project_gideon.repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
    InMemoryJobRepository,
)
from project_gideon.services import (
    ApplicationCampaignError,
    ApplicationCampaignService,
)


TENANT_ID = "tenant_1"
JOB_ID = "job_1"
CANDIDATE_ID = "candidate_1"


def make_job(
    *,
    tenant_id: str = TENANT_ID,
) -> Job:
    return Job(
        id=JOB_ID,
        tenant_id=tenant_id,
        source="test",
        source_job_id="source_job_1",
        source_url="https://example.com/jobs/1",
        application_url="https://example.com/jobs/1/apply",
        title="Network Engineer",
        company="Example",
        description="Example role",
    )


def make_candidate(
    *,
    tenant_id: str = TENANT_ID,
) -> CandidateProfile:
    return CandidateProfile(
        id=CANDIDATE_ID,
        tenant_id=tenant_id,
        identity=CandidateIdentity(
            first_name="Test",
            last_name="Candidate",
            email="candidate@example.com",
        ),
    )


async def make_service():
    jobs = InMemoryJobRepository()
    candidates = InMemoryCandidateRepository()
    applications = InMemoryApplicationRepository()

    await jobs.save(
        make_job()
    )

    await candidates.save(
        make_candidate()
    )

    service = ApplicationCampaignService(
        jobs=jobs,
        candidates=candidates,
        applications=applications,
    )

    return (
        service,
        jobs,
        candidates,
        applications,
    )


@pytest.mark.asyncio
async def test_shortlist_creates_durable_application():
    service, _, _, applications = await make_service()

    application = await service.shortlist(
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    assert (
        application.state
        is ApplicationState.SHORTLISTED
    )

    assert application.job_id == JOB_ID
    assert application.candidate_id == CANDIDATE_ID

    persisted = await applications.get(
        application.id,
        TENANT_ID,
    )

    assert persisted == application


@pytest.mark.asyncio
async def test_shortlist_is_idempotent_for_same_campaign():
    service, _, _, applications = await make_service()

    first = await service.shortlist(
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    second = await service.shortlist(
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    assert second.id == first.id
    assert second.state is ApplicationState.SHORTLISTED

    records = await applications.list_for_tenant(
        TENANT_ID
    )

    assert len(records) == 1


@pytest.mark.asyncio
async def test_shortlist_requires_canonical_job():
    service, _, _, _ = await make_service()

    with pytest.raises(KeyError):
        await service.shortlist(
            tenant_id=TENANT_ID,
            job_id="missing_job",
            candidate_id=CANDIDATE_ID,
        )


@pytest.mark.asyncio
async def test_shortlist_requires_canonical_candidate():
    service, _, _, _ = await make_service()

    with pytest.raises(KeyError):
        await service.shortlist(
            tenant_id=TENANT_ID,
            job_id=JOB_ID,
            candidate_id="missing_candidate",
        )


@pytest.mark.asyncio
async def test_start_preparation_transitions_shortlisted_application():
    service, _, _, applications = await make_service()

    shortlisted = await service.shortlist(
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    preparing = await service.start_preparation(
        application_id=shortlisted.id,
        tenant_id=TENANT_ID,
    )

    assert preparing.state is ApplicationState.PREPARING

    persisted = await applications.get(
        preparing.id,
        TENANT_ID,
    )

    assert persisted.state is ApplicationState.PREPARING


@pytest.mark.asyncio
async def test_start_preparation_is_idempotent():
    service, _, _, _ = await make_service()

    shortlisted = await service.shortlist(
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    first = await service.start_preparation(
        application_id=shortlisted.id,
        tenant_id=TENANT_ID,
    )

    second = await service.start_preparation(
        application_id=shortlisted.id,
        tenant_id=TENANT_ID,
    )

    assert second.id == first.id
    assert second.state is ApplicationState.PREPARING


@pytest.mark.asyncio
async def test_start_preparation_rejects_discovered_application():
    service, _, _, applications = await make_service()

    discovered = JobApplication(
        id="application_discovered",
        tenant_id=TENANT_ID,
        job_id=JOB_ID,
        candidate_id=CANDIDATE_ID,
    )

    await applications.save(
        discovered
    )

    with pytest.raises(
        ApplicationCampaignError,
        match="state=discovered",
    ):
        await service.start_preparation(
            application_id=discovered.id,
            tenant_id=TENANT_ID,
        )
