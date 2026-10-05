from __future__ import annotations

from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from project_gideon.models.application import (
    ApplicationState,
    JobApplication,
)
from project_gideon.models.approval import (
    ApprovalAction,
    ApprovalState,
)
from project_gideon.repositories.memory import (
    InMemoryApplicationRepository,
    InMemoryApprovalRepository,
)
from project_gideon.services.approval import (
    ApprovalService,
)
from project_gideon.services.application_review import (
    APPLICATION_REVIEW_FINGERPRINT_KEY,
    application_review_fingerprint,
)
from project_gideon.services.application_submission import (
    ApplicationSubmissionService,
    SubmissionApprovalInvalid,
    SubmissionEvidence,
)


class CountingActuator:
    def __init__(self):
        self.calls = 0

    async def submit(
        self,
        *,
        application,
    ):
        self.calls += 1

        return SubmissionEvidence(
            confirmed=True,
            confirmation_reference="fixture-review-binding",
        )


def make_application(
    *,
    state=ApplicationState.READY_FOR_REVIEW,
):
    return JobApplication(
        id="application_review",
        tenant_id="tenant_review",
        job_id="job_review",
        candidate_id="candidate_review",
        state=state,
        browser_session_id="browser_session_review",
        cv_file_id="cv_review",
        cover_letter_file_id="cover_review",
        meta_data={
            "prepared_fields": {
                "first_name": "Francis",
                "location": "Example",
            },
        },
    )


@pytest.mark.asyncio
async def test_approval_service_propagates_request_metadata_into_grant():
    approvals = InMemoryApprovalRepository()
    service = ApprovalService(approvals)

    request = await service.request(
        tenant_id="tenant_meta",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_meta",
        meta_data={
            APPLICATION_REVIEW_FINGERPRINT_KEY:
                "abc123",
            "fixture":
                "preserved",
        },
    )

    grant = await service.approve(
        approval_id=request.id,
        tenant_id=request.tenant_id,
    )

    assert (
        request.meta_data[
            APPLICATION_REVIEW_FINGERPRINT_KEY
        ]
        == "abc123"
    )

    assert (
        grant.meta_data
        == request.meta_data
    )


def test_review_fingerprint_ignores_workflow_state_and_timestamps():
    application = make_application()

    original = application_review_fingerprint(
        application
    )

    changed_workflow_only = application.model_copy(
        update={
            "state":
                ApplicationState.APPROVED,

            "updated_at":
                datetime.now(timezone.utc)
                + timedelta(
                    minutes=5
                ),

            "submitted_at":
                datetime.now(timezone.utc),
        }
    )

    assert (
        application_review_fingerprint(
            changed_workflow_only
        )
        == original
    )


def test_review_fingerprint_changes_when_reviewed_content_changes():
    application = make_application()

    original = application_review_fingerprint(
        application
    )

    changed_cv = application.model_copy(
        update={
            "cv_file_id":
                "different_cv",
        }
    )

    assert (
        application_review_fingerprint(
            changed_cv
        )
        != original
    )

    changed_metadata = application.model_copy(
        update={
            "meta_data": {
                "prepared_fields": {
                    "first_name":
                        "Different",
                    "location":
                        "Example",
                },
            },
        }
    )

    assert (
        application_review_fingerprint(
            changed_metadata
        )
        != original
    )


@pytest.mark.asyncio
async def test_approval_request_is_bound_to_exact_review_fingerprint():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()
    actuator = CountingActuator()

    application = make_application()

    await applications.save(
        application
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    request = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    expected = application_review_fingerprint(
        application
    )

    assert (
        request.meta_data[
            APPLICATION_REVIEW_FINGERPRINT_KEY
        ]
        == expected
    )

    approved = await service.approve_submission(
        approval_id=request.id,
        tenant_id=application.tenant_id,
    )

    assert (
        approved.grant.meta_data[
            APPLICATION_REVIEW_FINGERPRINT_KEY
        ]
        == expected
    )

    assert actuator.calls == 0


@pytest.mark.asyncio
async def test_application_change_after_request_blocks_human_approval():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()
    actuator = CountingActuator()

    application = make_application()

    await applications.save(
        application
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    request = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    changed = application.model_copy(
        update={
            "cv_file_id":
                "cv_changed_after_review",
        }
    )

    await applications.save(
        changed
    )

    with pytest.raises(
        SubmissionApprovalInvalid,
        match="stale",
    ):
        await service.approve_submission(
            approval_id=request.id,
            tenant_id=application.tenant_id,
        )

    persisted_request = await approvals.get(
        request.id,
        application.tenant_id,
    )

    assert (
        persisted_request.state
        is ApprovalState.PENDING
    )

    assert actuator.calls == 0


@pytest.mark.asyncio
async def test_application_change_after_human_approval_blocks_submission_without_consuming_grant():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()
    actuator = CountingActuator()

    application = make_application()

    await applications.save(
        application
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    request = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    approved = await service.approve_submission(
        approval_id=request.id,
        tenant_id=application.tenant_id,
    )

    stored = await applications.get(
        application.id,
        application.tenant_id,
    )

    changed = stored.model_copy(
        update={
            "cover_letter_file_id":
                "cover_changed_after_approval",
        }
    )

    await applications.save(
        changed
    )

    with pytest.raises(
        SubmissionApprovalInvalid,
        match="stale",
    ):
        await service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=approved.grant.id,
        )

    grant = await approvals.get_grant(
        approved.grant.id,
        application.tenant_id,
    )

    assert grant.is_consumed is False
    assert actuator.calls == 0


@pytest.mark.asyncio
async def test_same_review_revision_still_submits_normally():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()
    actuator = CountingActuator()

    application = make_application()

    await applications.save(
        application
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    request = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    approved = await service.approve_submission(
        approval_id=request.id,
        tenant_id=application.tenant_id,
    )

    result = await service.submit(
        application_id=application.id,
        tenant_id=application.tenant_id,
        grant_id=approved.grant.id,
    )

    assert (
        result.application.state
        is ApplicationState.SUBMITTED
    )

    assert result.grant.is_consumed is True
    assert actuator.calls == 1


@pytest.mark.asyncio
async def test_new_revision_gets_distinct_pending_approval_request():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()
    actuator = CountingActuator()

    application = make_application()

    await applications.save(
        application
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    first = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    changed = application.model_copy(
        update={
            "cv_file_id":
                "cv_new_revision",
        }
    )

    await applications.save(
        changed
    )

    second = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    assert second.id != first.id

    assert (
        second.meta_data[
            APPLICATION_REVIEW_FINGERPRINT_KEY
        ]
        != first.meta_data[
            APPLICATION_REVIEW_FINGERPRINT_KEY
        ]
    )
