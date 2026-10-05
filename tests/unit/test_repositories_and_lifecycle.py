import pytest

from project_gideon.models import (
    ApplicationState,
    CandidateIdentity,
    CandidateProfile,
    JobApplication,
)
from project_gideon.repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
)
from project_gideon.services import (
    ApplicationLifecycleService,
    InvalidApplicationTransition,
)


@pytest.mark.asyncio
async def test_candidate_repository_is_tenant_isolated():
    repository = InMemoryCandidateRepository()

    candidate = CandidateProfile(
        id="candidate_1",
        tenant_id="tenant_a",
        identity=CandidateIdentity(
            first_name="Test",
            last_name="Candidate",
            email="test@example.com",
        ),
    )

    await repository.save(candidate)

    retrieved = await repository.get(
        candidate.id,
        "tenant_a",
    )

    assert retrieved == candidate

    with pytest.raises(KeyError):
        await repository.get(
            candidate.id,
            "tenant_b",
        )


@pytest.mark.asyncio
async def test_legal_application_transition_is_persisted():
    repository = InMemoryApplicationRepository()

    application = JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
    )

    await repository.save(application)

    lifecycle = ApplicationLifecycleService(repository)

    updated = await lifecycle.transition(
        application_id=application.id,
        tenant_id=application.tenant_id,
        target=ApplicationState.SHORTLISTED,
    )

    assert updated.state is ApplicationState.SHORTLISTED
    assert updated.updated_at.tzinfo is not None


@pytest.mark.asyncio
async def test_illegal_application_transition_is_rejected():
    repository = InMemoryApplicationRepository()

    application = JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
    )

    await repository.save(application)

    lifecycle = ApplicationLifecycleService(repository)

    with pytest.raises(
        InvalidApplicationTransition,
        match="discovered -> submitted",
    ):
        await lifecycle.transition(
            application_id=application.id,
            tenant_id=application.tenant_id,
            target=ApplicationState.SUBMITTED,
        )


@pytest.mark.asyncio
async def test_approved_application_must_pass_through_submitting():
    from project_gideon.models.application import (
        ApplicationState,
        JobApplication,
    )
    from project_gideon.repositories.memory import (
        InMemoryApplicationRepository,
    )
    from project_gideon.services.application_lifecycle import (
        ApplicationLifecycleService,
        InvalidApplicationTransition,
    )

    repository = InMemoryApplicationRepository()

    application = JobApplication(
        id="application_submission_lifecycle",
        tenant_id="tenant_submission_lifecycle",
        job_id="job_submission_lifecycle",
        candidate_id="candidate_submission_lifecycle",
        state=ApplicationState.APPROVED,
    )

    await repository.save(
        application
    )

    lifecycle = ApplicationLifecycleService(
        repository
    )

    with pytest.raises(
        InvalidApplicationTransition,
        match="approved -> submitted",
    ):
        await lifecycle.transition(
            application_id=application.id,
            tenant_id=application.tenant_id,
            target=ApplicationState.SUBMITTED,
        )

    submitting = await lifecycle.claim_transition(
        application_id=application.id,
        tenant_id=application.tenant_id,
        target=ApplicationState.SUBMITTING,
    )

    assert (
        submitting.state
        is ApplicationState.SUBMITTING
    )

    assert submitting.submitted_at is None

    submitted = await lifecycle.claim_transition(
        application_id=application.id,
        tenant_id=application.tenant_id,
        target=ApplicationState.SUBMITTED,
    )

    assert (
        submitted.state
        is ApplicationState.SUBMITTED
    )

    assert submitted.submitted_at is not None
    assert submitted.submitted_at.tzinfo is not None
