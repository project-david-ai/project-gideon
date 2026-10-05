from __future__ import annotations

import pytest

from project_gideon.models.application import (
    ApplicationState,
    JobApplication,
)
from project_gideon.repositories.memory import (
    InMemoryApplicationRepository,
    InMemoryApprovalRepository,
)
from project_gideon.services.application_submission import (
    ApplicationSubmissionService,
    SubmissionConfirmationMissing,
)
from project_gideon.services.application_review import (
    application_review_fingerprint,
)
from project_gideon.services.reviewed_browser_submission import (
    BrowserSubmissionEvidenceInvalid,
    ReviewedBrowserSubmissionActuator,
    ReviewedSubmitConfirmation,
    ReviewedSubmitControl,
)


class FakeReviewedSubmissionBrowser:
    def __init__(
        self,
        *,
        inspected=None,
        confirmation=None,
        activation_error=None,
    ):
        self.inspected = inspected
        self.confirmation = confirmation
        self.activation_error = activation_error

        self.inspect_calls = 0
        self.activation_calls = 0

        self.last_expected_review_fingerprint = None

    async def inspect_submit_boundary(
        self,
        *,
        application_id,
        tenant_id,
        browser_session_id,
        expected_review_fingerprint,
    ):
        self.inspect_calls += 1

        self.last_expected_review_fingerprint = (
            expected_review_fingerprint
        )

        return self.inspected

    async def activate_submit_once(
        self,
        *,
        evidence,
    ):
        self.activation_calls += 1

        assert evidence is self.inspected

        if self.activation_error is not None:
            raise self.activation_error

        return self.confirmation


def make_application(
    *,
    state=ApplicationState.SUBMITTING,
):
    return JobApplication(
        id="application_browser_submit",
        tenant_id="tenant_browser_submit",
        job_id="job_browser_submit",
        candidate_id="candidate_browser_submit",
        state=state,
        browser_session_id="session_exact",
        cv_file_id="cv_exact",
        meta_data={
            "prepared_fields": {
                "name": "Francis",
            },
        },
    )


def valid_inspection(
    application,
):
    return ReviewedSubmitControl(
        browser_session_id=(
            application.browser_session_id
        ),
        page_url=(
            "https://example.test/application"
        ),
        control_ref="submit-ref-42",
        control_role="button",
        control_name="Submit application",
        snapshot_fingerprint="snapshot-pre-submit-001",
        application_review_fingerprint=(
            application_review_fingerprint(
                application
            )
        ),
        unique=True,
        enabled=True,
    )


def valid_confirmation():
    return ReviewedSubmitConfirmation(
        confirmed=True,
        snapshot_fingerprint=(
            "snapshot-pre-submit-001"
        ),
        confirmation_reference=(
            "confirmation-fixture-001"
        ),
        page_url=(
            "https://example.test/application/complete"
        ),
        meta_data={
            "fixture":
                "confirmed",
        },
    )


@pytest.mark.asyncio
async def test_reviewed_actuator_uses_one_inspection_and_one_activation():
    application = make_application()

    browser = FakeReviewedSubmissionBrowser(
        inspected=valid_inspection(
            application
        ),
        confirmation=valid_confirmation(),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    evidence = await actuator.submit(
        application=application
    )

    assert browser.inspect_calls == 1
    assert browser.activation_calls == 1

    assert evidence.confirmed is True

    assert (
        evidence.confirmation_reference
        == "confirmation-fixture-001"
    )


@pytest.mark.asyncio
async def test_browser_session_mismatch_blocks_activation():
    application = make_application()

    inspected = valid_inspection(
        application
    )

    inspected = ReviewedSubmitControl(
        **{
            **inspected.__dict__,
            "browser_session_id":
                "different-session",
        }
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=valid_confirmation(),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        BrowserSubmissionEvidenceInvalid,
        match="different browser session",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.inspect_calls == 1
    assert browser.activation_calls == 0


@pytest.mark.asyncio
async def test_review_fingerprint_mismatch_blocks_activation():
    application = make_application()

    inspected = valid_inspection(
        application
    )

    inspected = ReviewedSubmitControl(
        **{
            **inspected.__dict__,
            "application_review_fingerprint":
                "0" * 64,
        }
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=valid_confirmation(),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        BrowserSubmissionEvidenceInvalid,
        match="does not match",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.activation_calls == 0


@pytest.mark.asyncio
async def test_non_unique_submit_control_blocks_activation():
    application = make_application()

    inspected = valid_inspection(
        application
    )

    inspected = ReviewedSubmitControl(
        **{
            **inspected.__dict__,
            "unique":
                False,
        }
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=valid_confirmation(),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        BrowserSubmissionEvidenceInvalid,
        match="not unique",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.activation_calls == 0


@pytest.mark.asyncio
async def test_disabled_submit_control_blocks_activation():
    application = make_application()

    inspected = valid_inspection(
        application
    )

    inspected = ReviewedSubmitControl(
        **{
            **inspected.__dict__,
            "enabled":
                False,
        }
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=valid_confirmation(),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        BrowserSubmissionEvidenceInvalid,
        match="disabled",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.activation_calls == 0


@pytest.mark.asyncio
async def test_confirmation_must_bind_to_inspected_snapshot():
    application = make_application()

    browser = FakeReviewedSubmissionBrowser(
        inspected=valid_inspection(
            application
        ),
        confirmation=ReviewedSubmitConfirmation(
            confirmed=True,
            snapshot_fingerprint=(
                "different-snapshot"
            ),
            confirmation_reference=(
                "should-not-be-accepted"
            ),
        ),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        BrowserSubmissionEvidenceInvalid,
        match="not bound",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.activation_calls == 1


@pytest.mark.asyncio
async def test_activation_failure_is_never_retried():
    application = make_application()

    browser = FakeReviewedSubmissionBrowser(
        inspected=valid_inspection(
            application
        ),
        confirmation=valid_confirmation(),
        activation_error=RuntimeError(
            "ambiguous fixture activation failure"
        ),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    with pytest.raises(
        RuntimeError,
        match="ambiguous fixture",
    ):
        await actuator.submit(
            application=application
        )

    assert browser.inspect_calls == 1
    assert browser.activation_calls == 1


@pytest.mark.asyncio
async def test_unconfirmed_browser_result_is_returned_not_retried():
    application = make_application()

    browser = FakeReviewedSubmissionBrowser(
        inspected=valid_inspection(
            application
        ),
        confirmation=ReviewedSubmitConfirmation(
            confirmed=False,
            snapshot_fingerprint=(
                "snapshot-pre-submit-001"
            ),
            page_url=(
                "https://example.test/application"
            ),
        ),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
    )

    evidence = await actuator.submit(
        application=application
    )

    assert evidence.confirmed is False
    assert browser.activation_calls == 1


@pytest.mark.asyncio
async def test_full_domain_transaction_uses_reviewed_browser_actuator_once():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()

    application = JobApplication(
        id="application_integrated_browser",
        tenant_id="tenant_integrated_browser",
        job_id="job_integrated_browser",
        candidate_id="candidate_integrated_browser",
        state=ApplicationState.READY_FOR_REVIEW,
        browser_session_id="session_integrated",
        cv_file_id="cv_integrated",
    )

    await applications.save(
        application
    )

    inspected = ReviewedSubmitControl(
        browser_session_id="session_integrated",
        page_url="https://example.test/apply",
        control_ref="submit-integrated-ref",
        control_role="button",
        control_name="Submit application",
        snapshot_fingerprint="integrated-pre-submit",
        application_review_fingerprint=(
            application_review_fingerprint(
                application
            )
        ),
        unique=True,
        enabled=True,
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=ReviewedSubmitConfirmation(
            confirmed=True,
            snapshot_fingerprint=(
                "integrated-pre-submit"
            ),
            confirmation_reference=(
                "integrated-confirmation"
            ),
            page_url=(
                "https://example.test/complete"
            ),
        ),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
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

    assert browser.inspect_calls == 1
    assert browser.activation_calls == 1


@pytest.mark.asyncio
async def test_full_domain_transaction_leaves_submitting_on_unconfirmed_browser_result():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()

    application = JobApplication(
        id="application_unconfirmed_browser",
        tenant_id="tenant_unconfirmed_browser",
        job_id="job_unconfirmed_browser",
        candidate_id="candidate_unconfirmed_browser",
        state=ApplicationState.READY_FOR_REVIEW,
        browser_session_id="session_unconfirmed",
    )

    await applications.save(
        application
    )

    inspected = ReviewedSubmitControl(
        browser_session_id="session_unconfirmed",
        page_url="https://example.test/apply",
        control_ref="submit-unconfirmed-ref",
        control_role="button",
        control_name="Submit application",
        snapshot_fingerprint="unconfirmed-pre-submit",
        application_review_fingerprint=(
            application_review_fingerprint(
                application
            )
        ),
        unique=True,
        enabled=True,
    )

    browser = FakeReviewedSubmissionBrowser(
        inspected=inspected,
        confirmation=ReviewedSubmitConfirmation(
            confirmed=False,
            snapshot_fingerprint=(
                "unconfirmed-pre-submit"
            ),
        ),
    )

    actuator = ReviewedBrowserSubmissionActuator(
        browser
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

    with pytest.raises(
        SubmissionConfirmationMissing,
    ):
        await service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=approved.grant.id,
        )

    stored = await applications.get(
        application.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTING
    )

    assert browser.activation_calls == 1
