from datetime import datetime, timedelta, timezone

import pytest

from project_gideon.models import (
    ApprovalAction,
    ApprovalState,
    ApplicationState,
    JobApplication,
)
from project_gideon.repositories import InMemoryApprovalRepository
from project_gideon.services import (
    ApprovalGrantInvalid,
    ApprovalNotPending,
    ApprovalService,
    SubmissionGuard,
    SubmissionNotAllowed,
)


@pytest.mark.asyncio
async def test_approval_request_can_be_approved():
    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
        summary="Submit application.",
    )

    assert request.state is ApprovalState.PENDING

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    persisted = await repository.get(
        request.id,
        request.tenant_id,
    )

    assert persisted.state is ApprovalState.APPROVED
    assert persisted.resolved_at is not None

    assert grant.tenant_id == request.tenant_id
    assert grant.action is request.action
    assert grant.resource_id == request.resource_id
    assert grant.is_consumed is False


@pytest.mark.asyncio
async def test_non_pending_request_cannot_be_approved_again():
    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    with pytest.raises(ApprovalNotPending):
        await service.approve(
            approval_id=request.id,
            tenant_id=request.tenant_id,
        )


def test_expired_grant_is_rejected():
    now = datetime.now(timezone.utc)

    from project_gideon.models import ApprovalGrant

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
        issued_at=now - timedelta(minutes=30),
        expires_at=now - timedelta(minutes=15),
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="expired",
    ):
        ApprovalService.validate_grant(
            grant,
            tenant_id="tenant_1",
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id="application_1",
            now=now,
        )


def test_consumed_grant_is_rejected():
    now = datetime.now(timezone.utc)

    from project_gideon.models import ApprovalGrant

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
        consumed_at=now,
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="consumed",
    ):
        ApprovalService.validate_grant(
            grant,
            tenant_id="tenant_1",
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id="application_1",
            now=now,
        )


def test_submission_guard_requires_approved_application():
    now = datetime.now(timezone.utc)

    from project_gideon.models import ApprovalGrant

    application = JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
        state=ApplicationState.READY_FOR_REVIEW,
    )

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id=application.id,
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
    )

    with pytest.raises(
        SubmissionNotAllowed,
        match="not approved",
    ):
        SubmissionGuard.authorize(
            application=application,
            grant=grant,
        )


def test_submission_guard_rejects_wrong_resource():
    now = datetime.now(timezone.utc)

    from project_gideon.models import ApprovalGrant

    application = JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
        state=ApplicationState.APPROVED,
    )

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_other",
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="resource mismatch",
    ):
        SubmissionGuard.authorize(
            application=application,
            grant=grant,
        )


def test_submission_guard_accepts_correct_scope():
    now = datetime.now(timezone.utc)

    from project_gideon.models import ApprovalGrant

    application = JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
        state=ApplicationState.APPROVED,
    )

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id=application.id,
        issued_at=now,
        expires_at=now + timedelta(minutes=15),
    )

    SubmissionGuard.authorize(
        application=application,
        grant=grant,
    )


@pytest.mark.asyncio
async def test_approved_grant_is_persisted():
    from project_gideon.models.approval import (
        ApprovalAction,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalService,
    )

    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
        summary="Submit application.",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    persisted = await repository.get_grant(
        grant.id,
        request.tenant_id,
    )

    assert persisted == grant
    assert persisted.is_consumed is False


@pytest.mark.asyncio
async def test_persisted_grant_can_be_consumed_exactly_once():
    from project_gideon.models.approval import (
        ApprovalAction,
        ApprovalState,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalGrantInvalid,
        ApprovalService,
    )

    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    consumed = await service.consume(
        grant_id=grant.id,
        tenant_id=request.tenant_id,
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    assert consumed.is_consumed is True

    persisted_grant = await repository.get_grant(
        grant.id,
        request.tenant_id,
    )

    assert persisted_grant.is_consumed is True

    persisted_request = await repository.get(
        request.id,
        request.tenant_id,
    )

    assert (
        persisted_request.state
        is ApprovalState.CONSUMED
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="consumed",
    ):
        await service.consume(
            grant_id=grant.id,
            tenant_id=request.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id="application_1",
        )


@pytest.mark.asyncio
async def test_persisted_grant_cannot_cross_application_boundary():
    from project_gideon.models.approval import (
        ApprovalAction,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalGrantInvalid,
        ApprovalService,
    )

    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="resource mismatch",
    ):
        await service.consume(
            grant_id=grant.id,
            tenant_id=request.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id="application_OTHER",
        )

    persisted = await repository.get_grant(
        grant.id,
        request.tenant_id,
    )

    assert persisted.is_consumed is False


@pytest.mark.asyncio
async def test_nonapproved_parent_request_cannot_consume_grant():
    from project_gideon.models.approval import (
        ApprovalAction,
        ApprovalState,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalGrantInvalid,
        ApprovalService,
    )

    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    tampered_request = request.model_copy(
        update={
            "state": ApprovalState.REJECTED,
        }
    )

    await repository.save(
        tampered_request
    )

    with pytest.raises(
        ApprovalGrantInvalid,
        match="not in approved state",
    ):
        await service.consume(
            grant_id=grant.id,
            tenant_id=request.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id="application_1",
        )

    persisted = await repository.get_grant(
        grant.id,
        request.tenant_id,
    )

    assert persisted.is_consumed is False


@pytest.mark.asyncio
async def test_repository_grant_claim_is_single_use():
    from project_gideon.models.approval import (
        ApprovalAction,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalService,
    )

    repository = InMemoryApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_atomic",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_atomic",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    consumed = service.consume_grant(
        grant
    )

    first = await repository.claim_grant(
        consumed
    )

    second = await repository.claim_grant(
        consumed
    )

    assert first is not None
    assert first.is_consumed is True
    assert second is None


@pytest.mark.asyncio
async def test_concurrent_service_consumers_cannot_both_claim_same_grant():
    import asyncio

    from project_gideon.models.approval import (
        ApprovalAction,
    )
    from project_gideon.repositories.memory import (
        InMemoryApprovalRepository,
    )
    from project_gideon.services.approval import (
        ApprovalGrantInvalid,
        ApprovalService,
    )

    class RacingApprovalRepository(
        InMemoryApprovalRepository
    ):
        def __init__(self):
            super().__init__()

            self._consume_readers = 0
            self._release_consumers = (
                asyncio.Event()
            )

            self._race_grant_id = None

        async def get_grant(
            self,
            grant_id,
            tenant_id,
        ):
            grant = await super().get_grant(
                grant_id,
                tenant_id,
            )

            if (
                self._race_grant_id == grant_id
                and not grant.is_consumed
            ):
                self._consume_readers += 1

                if self._consume_readers >= 2:
                    self._release_consumers.set()

                await self._release_consumers.wait()

            return grant

    repository = RacingApprovalRepository()
    service = ApprovalService(repository)

    request = await service.request(
        tenant_id="tenant_race",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_race",
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    repository._race_grant_id = grant.id

    results = await asyncio.gather(
        service.consume(
            grant_id=grant.id,
            tenant_id=request.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id=request.resource_id,
        ),
        service.consume(
            grant_id=grant.id,
            tenant_id=request.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id=request.resource_id,
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
    assert successes[0].is_consumed is True

    assert len(failures) == 1
    assert isinstance(
        failures[0],
        ApprovalGrantInvalid,
    )

    # The losing concurrent caller may be rejected by either
    # authoritative single-use barrier:
    #
    #   1. the persisted grant was already claimed, or
    #   2. the parent ApprovalRequest was already moved from
    #      APPROVED to CONSUMED by the winning caller.
    #
    # Both prove that only one caller acquired submission authority.
    message = str(
        failures[0]
    ).lower()

    assert (
        "consumed" in message
        or "not in approved state" in message
    )
