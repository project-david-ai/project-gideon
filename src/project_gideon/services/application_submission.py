from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from project_gideon.models.application import (
    ApplicationState,
    JobApplication,
)
from project_gideon.models.approval import (
    ApprovalAction,
    ApprovalGrant,
    ApprovalRequest,
    ApprovalState,
)
from project_gideon.ports import (
    ApplicationRepository,
    ApprovalRepository,
)
from project_gideon.services.approval import (
    ApprovalService,
)
from project_gideon.services.application_lifecycle import (
    ApplicationLifecycleService,
    InvalidApplicationTransition,
)
from project_gideon.services.submission_guard import (
    SubmissionGuard,
)


class ApplicationSubmissionError(RuntimeError):
    pass


class SubmissionNotReady(ApplicationSubmissionError):
    pass


class SubmissionApprovalInvalid(ApplicationSubmissionError):
    pass


class SubmissionConfirmationMissing(
    ApplicationSubmissionError
):
    pass


class SubmissionOutcomeUnknown(
    ApplicationSubmissionError
):
    """
    Submission may have crossed the external side-effect boundary.

    Automatic retry is forbidden.
    """


@dataclass(frozen=True)
class SubmissionEvidence:
    confirmed: bool

    confirmation_reference: str | None = None

    meta_data: dict[str, object] = field(
        default_factory=dict
    )


class ApplicationSubmissionActuator(Protocol):
    async def submit(
        self,
        *,
        application: JobApplication,
    ) -> SubmissionEvidence:
        ...


@dataclass(frozen=True)
class SubmissionApproval:
    application: JobApplication

    request: ApprovalRequest

    grant: ApprovalGrant


@dataclass(frozen=True)
class ApplicationSubmissionResult:
    application: JobApplication

    grant: ApprovalGrant

    evidence: SubmissionEvidence


class ApplicationSubmissionService:
    """
    Deterministic human-authorized submission boundary.

    The irreversible path is deliberately:

        APPROVED
            -> validate scoped grant
            -> atomically consume grant
            -> atomically claim SUBMITTING
            -> actuator
            -> confirmation evidence
            -> SUBMITTED

    Once either irreversible claim succeeds, automatic retries are
    not permitted on ambiguous outcomes.
    """

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        approvals: ApprovalRepository,
        actuator: ApplicationSubmissionActuator,
    ) -> None:
        self._applications = applications
        self._approvals = approvals
        self._actuator = actuator

        self._approval_service = ApprovalService(
            approvals
        )

        self._lifecycle = ApplicationLifecycleService(
            applications
        )

    @staticmethod
    def _validate_ready(
        application: JobApplication,
    ) -> None:
        if (
            application.state
            is not ApplicationState.READY_FOR_REVIEW
        ):
            raise SubmissionNotReady(
                "Application is not ready for review: "
                f"{application.state.value}"
            )

        unresolved_required = [
            question
            for question
            in application.unresolved_questions
            if question.required
        ]

        if unresolved_required:
            raise SubmissionNotReady(
                "Application still has unresolved "
                "required questions."
            )

    async def request_approval(
        self,
        *,
        application_id: str,
        tenant_id: str,
        requested_by_run_id: str | None = None,
        requested_by_assistant_id: str | None = None,
        summary: str | None = None,
    ) -> ApprovalRequest:
        application = await self._applications.get(
            application_id,
            tenant_id,
        )

        self._validate_ready(
            application
        )

        pending = [
            approval
            for approval
            in await self._approvals.list_for_tenant(
                tenant_id
            )
            if (
                approval.action
                is ApprovalAction.SUBMIT_APPLICATION
                and approval.resource_id
                == application.id
                and approval.state
                is ApprovalState.PENDING
            )
        ]

        if len(pending) > 1:
            raise SubmissionApprovalInvalid(
                "Multiple pending submission approvals "
                "exist for this application."
            )

        if pending:
            return pending[0]

        return await self._approval_service.request(
            tenant_id=tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id=application.id,
            requested_by_run_id=requested_by_run_id,
            requested_by_assistant_id=(
                requested_by_assistant_id
            ),
            summary=summary,
        )

    async def approve_submission(
        self,
        *,
        approval_id: str,
        tenant_id: str,
    ) -> SubmissionApproval:
        """
        Human-side authority mint.

        This method is intentionally not a Project David consumer tool.
        """

        request = await self._approvals.get(
            approval_id,
            tenant_id,
        )

        if (
            request.action
            is not ApprovalAction.SUBMIT_APPLICATION
        ):
            raise SubmissionApprovalInvalid(
                "Approval is not scoped to "
                "application submission."
            )

        application = await self._applications.get(
            request.resource_id,
            tenant_id,
        )

        self._validate_ready(
            application
        )

        grant = await self._approval_service.approve(
            approval_id=request.id,
            tenant_id=tenant_id,
        )

        try:
            approved = await self._lifecycle.claim_transition(
                application_id=application.id,
                tenant_id=tenant_id,
                target=ApplicationState.APPROVED,
            )
        except InvalidApplicationTransition as exc:
            # Fail closed.
            #
            # We deliberately do not invoke any external side effect.
            # A redundant grant is still scoped to this exact
            # application and cannot bypass the application-state CAS
            # used by submit().
            raise SubmissionApprovalInvalid(
                "Application approval state could not be claimed."
            ) from exc

        persisted_request = await self._approvals.get(
            request.id,
            tenant_id,
        )

        return SubmissionApproval(
            application=approved,
            request=persisted_request,
            grant=grant,
        )

    async def _record_submission(
        self,
        *,
        application: JobApplication,
        grant: ApprovalGrant,
        status: str,
        evidence: SubmissionEvidence | None = None,
        error: Exception | None = None,
    ) -> JobApplication:
        meta_data = dict(
            application.meta_data
        )

        submission = {
            "status": status,
            "approval_request_id":
                grant.approval_request_id,
            "grant_id":
                grant.id,
        }

        if evidence is not None:
            submission.update(
                {
                    "confirmed":
                        evidence.confirmed,
                    "confirmation_reference":
                        evidence.confirmation_reference,
                    "evidence":
                        dict(
                            evidence.meta_data
                        ),
                }
            )

        if error is not None:
            submission.update(
                {
                    "error_type":
                        type(error).__name__,
                    "error":
                        str(error),
                }
            )

        meta_data[
            "submission"
        ] = submission

        return await self._applications.save(
            application.model_copy(
                update={
                    "meta_data":
                        meta_data,
                }
            )
        )

    async def submit(
        self,
        *,
        application_id: str,
        tenant_id: str,
        grant_id: str,
    ) -> ApplicationSubmissionResult:
        application = await self._applications.get(
            application_id,
            tenant_id,
        )

        grant = await self._approvals.get_grant(
            grant_id,
            tenant_id,
        )

        SubmissionGuard.authorize(
            application=application,
            grant=grant,
        )

        # Barrier 1:
        # exactly one caller may consume this authority grant.
        consumed_grant = (
            await self._approval_service.consume(
                grant_id=grant.id,
                tenant_id=tenant_id,
                action=(
                    ApprovalAction.SUBMIT_APPLICATION
                ),
                resource_id=application.id,
            )
        )

        # Barrier 2:
        # even two independently valid grants cannot both claim the
        # application for an irreversible submission attempt.
        try:
            submitting = await self._lifecycle.claim_transition(
                application_id=application.id,
                tenant_id=tenant_id,
                target=ApplicationState.SUBMITTING,
            )
        except InvalidApplicationTransition as exc:
            raise ApplicationSubmissionError(
                "Submission authority was consumed but the "
                "application state claim was lost. "
                "Automatic retry is forbidden."
            ) from exc

        try:
            evidence = await self._actuator.submit(
                application=submitting,
            )
        except Exception as exc:
            await self._record_submission(
                application=submitting,
                grant=consumed_grant,
                status="outcome_unknown",
                error=exc,
            )

            raise SubmissionOutcomeUnknown(
                "Submission actuator failed after "
                "irreversible authority was claimed. "
                "Reconciliation is required before retry."
            ) from exc

        submitting = await self._record_submission(
            application=submitting,
            grant=consumed_grant,
            status=(
                "confirmed"
                if evidence.confirmed
                else "unconfirmed"
            ),
            evidence=evidence,
        )

        if not evidence.confirmed:
            raise SubmissionConfirmationMissing(
                "Submission actuator did not provide "
                "confirmation evidence. "
                "Automatic retry is forbidden."
            )

        try:
            submitted = await self._lifecycle.claim_transition(
                application_id=application.id,
                tenant_id=tenant_id,
                target=ApplicationState.SUBMITTED,
            )
        except InvalidApplicationTransition as exc:
            raise SubmissionOutcomeUnknown(
                "External submission was confirmed but durable "
                "SUBMITTED state could not be claimed. "
                "Manual reconciliation is required."
            ) from exc

        return ApplicationSubmissionResult(
            application=submitted,
            grant=consumed_grant,
            evidence=evidence,
        )
