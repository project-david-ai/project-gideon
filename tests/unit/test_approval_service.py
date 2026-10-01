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