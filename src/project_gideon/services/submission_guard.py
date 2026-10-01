from __future__ import annotations

from project_gideon.models import (
    ApprovalAction,
    ApprovalGrant,
    ApplicationState,
    JobApplication,
)
from project_gideon.services.approval import ApprovalService


class SubmissionNotAllowed(ValueError):
    pass


class SubmissionGuard:
    """
    Hard gate for externally consequential application submission.

    Submission requires both:
      1. application state == APPROVED
      2. a valid, unexpired, unconsumed approval grant scoped to the
         same tenant and application
    """

    @staticmethod
    def authorize(
        *,
        application: JobApplication,
        grant: ApprovalGrant,
    ) -> None:
        if application.state is not ApplicationState.APPROVED:
            raise SubmissionNotAllowed(
                f"Application is not approved: {application.state.value}"
            )

        ApprovalService.validate_grant(
            grant,
            tenant_id=application.tenant_id,
            action=ApprovalAction.SUBMIT_APPLICATION,
            resource_id=application.id,
        )