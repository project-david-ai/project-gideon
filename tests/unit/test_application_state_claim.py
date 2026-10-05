from __future__ import annotations

import asyncio

import pytest

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


@pytest.mark.asyncio
async def test_repository_application_state_claim_has_single_winner():
    repository = InMemoryApplicationRepository()

    original = JobApplication(
        id="application_atomic",
        tenant_id="tenant_atomic",
        job_id="job_atomic",
        candidate_id="candidate_atomic",
        state=ApplicationState.APPROVED,
    )

    await repository.save(
        original
    )

    candidate_a = original.model_copy(
        update={
            "state":
                ApplicationState.SUBMITTED,
        }
    )

    candidate_b = original.model_copy(
        update={
            "state":
                ApplicationState.SUBMITTED,
        }
    )

    results = await asyncio.gather(
        repository.claim_state(
            candidate_a,
            expected_state=(
                ApplicationState.APPROVED
            ),
        ),
        repository.claim_state(
            candidate_b,
            expected_state=(
                ApplicationState.APPROVED
            ),
        ),
    )

    winners = [
        result
        for result in results
        if result is not None
    ]

    losers = [
        result
        for result in results
        if result is None
    ]

    assert len(winners) == 1
    assert len(losers) == 1

    stored = await repository.get(
        original.id,
        original.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTED
    )


@pytest.mark.asyncio
async def test_lifecycle_atomic_transition_has_single_winner():
    repository = InMemoryApplicationRepository()

    application = JobApplication(
        id="application_lifecycle_race",
        tenant_id="tenant_lifecycle_race",
        job_id="job_race",
        candidate_id="candidate_race",
        state=ApplicationState.APPROVED,
    )

    await repository.save(
        application
    )

    lifecycle = ApplicationLifecycleService(
        repository
    )

    results = await asyncio.gather(
        lifecycle.claim_transition(
            application_id=application.id,
            tenant_id=application.tenant_id,
            target=ApplicationState.SUBMITTED,
        ),
        lifecycle.claim_transition(
            application_id=application.id,
            tenant_id=application.tenant_id,
            target=ApplicationState.SUBMITTED,
        ),
        return_exceptions=True,
    )

    successes = [
        result
        for result in results
        if not isinstance(
            result,
            Exception,
        )
    ]

    failures = [
        result
        for result in results
        if isinstance(
            result,
            Exception,
        )
    ]

    assert len(successes) == 1

    assert (
        successes[0].state
        is ApplicationState.SUBMITTED
    )

    assert len(failures) == 1

    assert isinstance(
        failures[0],
        InvalidApplicationTransition,
    )

    stored = await repository.get(
        application.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTED
    )

    assert stored.submitted_at is not None


@pytest.mark.asyncio
async def test_failed_state_claim_does_not_overwrite_winner():
    repository = InMemoryApplicationRepository()

    application = JobApplication(
        id="application_stale",
        tenant_id="tenant_stale",
        job_id="job_stale",
        candidate_id="candidate_stale",
        state=ApplicationState.APPROVED,
    )

    await repository.save(
        application
    )

    submitted = application.model_copy(
        update={
            "state":
                ApplicationState.SUBMITTED,
        }
    )

    first = await repository.claim_state(
        submitted,
        expected_state=ApplicationState.APPROVED,
    )

    assert first is not None

    stale = application.model_copy(
        update={
            "state":
                ApplicationState.FAILED,
        }
    )

    second = await repository.claim_state(
        stale,
        expected_state=ApplicationState.APPROVED,
    )

    assert second is None

    stored = await repository.get(
        application.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTED
    )
