from __future__ import annotations

import asyncio

import pytest

from project_gideon.models.application import (
    ApplicationState,
    JobApplication,
    UnresolvedQuestion,
)
from project_gideon.models.approval import (
    ApprovalAction,
)
from project_gideon.repositories.memory import (
    InMemoryApplicationRepository,
    InMemoryApprovalRepository,
)
from project_gideon.services.approval import (
    ApprovalService,
)
from project_gideon.services.application_submission import (
    ApplicationSubmissionError,
    ApplicationSubmissionService,
    SubmissionConfirmationMissing,
    SubmissionEvidence,
    SubmissionNotReady,
    SubmissionOutcomeUnknown,
)
from project_gideon.services.submission_guard import (
    SubmissionNotAllowed,
)


class FakeSubmissionActuator:
    def __init__(
        self,
        *,
        applications,
        approvals,
        grant_id_getter=None,
        evidence=None,
        error=None,
        yield_once=False,
    ):
        self.applications = applications
        self.approvals = approvals
        self.grant_id_getter = grant_id_getter

        self.evidence = (
            evidence
            or SubmissionEvidence(
                confirmed=True,
                confirmation_reference=(
                    "fixture-confirmation"
                ),
                meta_data={
                    "fixture": True,
                },
            )
        )

        self.error = error
        self.yield_once = yield_once

        self.calls = 0

    async def submit(
        self,
        *,
        application,
    ):
        self.calls += 1

        stored = await self.applications.get(
            application.id,
            application.tenant_id,
        )

        assert (
            stored.state
            is ApplicationState.SUBMITTING
        )

        if self.grant_id_getter is not None:
            grant_id = self.grant_id_getter()

            if grant_id is not None:
                grant = await self.approvals.get_grant(
                    grant_id,
                    application.tenant_id,
                )

                # Irreversible authority must already be consumed
                # before the actuator can execute.
                assert grant.is_consumed is True

        if self.yield_once:
            await asyncio.sleep(0)

        if self.error is not None:
            raise self.error

        return self.evidence


async def build_ready_service(
    *,
    unresolved_questions=None,
    evidence=None,
    error=None,
    yield_once=False,
):
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()

    application = JobApplication(
        id="application_fixture",
        tenant_id="tenant_fixture",
        job_id="job_fixture",
        candidate_id="candidate_fixture",
        state=ApplicationState.READY_FOR_REVIEW,
        unresolved_questions=(
            unresolved_questions
            or []
        ),
    )

    await applications.save(
        application
    )

    grant_holder = {
        "id": None,
    }

    actuator = FakeSubmissionActuator(
        applications=applications,
        approvals=approvals,
        grant_id_getter=lambda: (
            grant_holder["id"]
        ),
        evidence=evidence,
        error=error,
        yield_once=yield_once,
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    return (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    )


async def approve_ready_application(
    *,
    application,
    service,
    grant_holder,
):
    request = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
        summary=(
            "Submit reviewed fixture application."
        ),
    )

    approved = await service.approve_submission(
        approval_id=request.id,
        tenant_id=application.tenant_id,
    )

    grant_holder[
        "id"
    ] = approved.grant.id

    return approved


@pytest.mark.asyncio
async def test_human_approval_mints_grant_and_moves_application_to_approved():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service()

    approved = await approve_ready_application(
        application=application,
        service=service,
        grant_holder=grant_holder,
    )

    stored = await applications.get(
        application.id,
        application.tenant_id,
    )

    grant = await approvals.get_grant(
        approved.grant.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.APPROVED
    )

    assert grant.is_consumed is False

    assert actuator.calls == 0


@pytest.mark.asyncio
async def test_submission_consumes_grant_before_actuator_and_requires_confirmation():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service()

    approved = await approve_ready_application(
        application=application,
        service=service,
        grant_holder=grant_holder,
    )

    result = await service.submit(
        application_id=application.id,
        tenant_id=application.tenant_id,
        grant_id=approved.grant.id,
    )

    assert actuator.calls == 1

    assert (
        result.application.state
        is ApplicationState.SUBMITTED
    )

    assert (
        result.application.submitted_at
        is not None
    )

    assert result.grant.is_consumed is True

    stored = await applications.get(
        application.id,
        application.tenant_id,
    )

    assert (
        stored.meta_data[
            "submission"
        ][
            "confirmation_reference"
        ]
        == "fixture-confirmation"
    )

    assert (
        stored.meta_data[
            "submission"
        ][
            "status"
        ]
        == "confirmed"
    )


@pytest.mark.asyncio
async def test_same_grant_cannot_invoke_actuator_twice():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service()

    approved = await approve_ready_application(
        application=application,
        service=service,
        grant_holder=grant_holder,
    )

    await service.submit(
        application_id=application.id,
        tenant_id=application.tenant_id,
        grant_id=approved.grant.id,
    )

    with pytest.raises(
        SubmissionNotAllowed,
    ):
        await service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=approved.grant.id,
        )

    assert actuator.calls == 1


@pytest.mark.asyncio
async def test_actuator_exception_leaves_submitting_and_forbids_automatic_retry():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service(
        error=RuntimeError(
            "fixture transport failure"
        )
    )

    approved = await approve_ready_application(
        application=application,
        service=service,
        grant_holder=grant_holder,
    )

    with pytest.raises(
        SubmissionOutcomeUnknown,
        match="Reconciliation is required",
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

    grant = await approvals.get_grant(
        approved.grant.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTING
    )

    assert stored.submitted_at is None
    assert grant.is_consumed is True
    assert actuator.calls == 1

    assert (
        stored.meta_data[
            "submission"
        ][
            "status"
        ]
        == "outcome_unknown"
    )

    with pytest.raises(
        SubmissionNotAllowed,
    ):
        await service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=approved.grant.id,
        )

    assert actuator.calls == 1


@pytest.mark.asyncio
async def test_unconfirmed_result_never_marks_application_submitted():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service(
        evidence=SubmissionEvidence(
            confirmed=False,
            meta_data={
                "fixture":
                    "unconfirmed",
            },
        )
    )

    approved = await approve_ready_application(
        application=application,
        service=service,
        grant_holder=grant_holder,
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

    assert stored.submitted_at is None

    assert (
        stored.meta_data[
            "submission"
        ][
            "status"
        ]
        == "unconfirmed"
    )

    assert actuator.calls == 1


@pytest.mark.asyncio
async def test_required_unknown_answer_blocks_approval_request():
    question = UnresolvedQuestion(
        field_id="work_authorization",
        question=(
            "Are you authorized to work?"
        ),
        reason=(
            "Candidate authority required."
        ),
        required=True,
    )

    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service(
        unresolved_questions=[
            question,
        ]
    )

    with pytest.raises(
        SubmissionNotReady,
        match="unresolved required",
    ):
        await service.request_approval(
            application_id=application.id,
            tenant_id=application.tenant_id,
        )

    assert actuator.calls == 0


@pytest.mark.asyncio
async def test_pending_submission_approval_request_is_idempotent():
    (
        applications,
        approvals,
        application,
        service,
        actuator,
        grant_holder,
    ) = await build_ready_service()

    first = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    second = await service.request_approval(
        application_id=application.id,
        tenant_id=application.tenant_id,
    )

    assert second.id == first.id

    pending = await approvals.list_for_tenant(
        application.tenant_id
    )

    assert len(pending) == 1


@pytest.mark.asyncio
async def test_two_independent_valid_grants_still_produce_one_actuator_call():
    applications = InMemoryApplicationRepository()
    approvals = InMemoryApprovalRepository()

    application = JobApplication(
        id="application_two_grants",
        tenant_id="tenant_two_grants",
        job_id="job_two_grants",
        candidate_id="candidate_two_grants",
        state=ApplicationState.APPROVED,
    )

    await applications.save(
        application
    )

    authority = ApprovalService(
        approvals
    )

    request_a = await authority.request(
        tenant_id=application.tenant_id,
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id=application.id,
    )

    grant_a = await authority.approve(
        approval_id=request_a.id,
        tenant_id=application.tenant_id,
    )

    request_b = await authority.request(
        tenant_id=application.tenant_id,
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id=application.id,
    )

    grant_b = await authority.approve(
        approval_id=request_b.id,
        tenant_id=application.tenant_id,
    )

    actuator = FakeSubmissionActuator(
        applications=applications,
        approvals=approvals,
        yield_once=True,
    )

    service = ApplicationSubmissionService(
        applications=applications,
        approvals=approvals,
        actuator=actuator,
    )

    results = await asyncio.gather(
        service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=grant_a.id,
        ),
        service.submit(
            application_id=application.id,
            tenant_id=application.tenant_id,
            grant_id=grant_b.id,
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
    assert len(failures) == 1

    assert isinstance(
        failures[0],
        (
            ApplicationSubmissionError,
            SubmissionNotAllowed,
        ),
    )

    assert actuator.calls == 1

    stored = await applications.get(
        application.id,
        application.tenant_id,
    )

    assert (
        stored.state
        is ApplicationState.SUBMITTED
    )
