from __future__ import annotations

import hmac
from dataclasses import (
    dataclass,
    field,
)
from typing import Protocol

from project_gideon.models.application import (
    JobApplication,
)
from project_gideon.services.application_review import (
    application_review_fingerprint,
)
from project_gideon.services.application_submission import (
    SubmissionEvidence,
)


class ReviewedBrowserSubmissionError(RuntimeError):
    pass


class BrowserSubmissionEvidenceInvalid(
    ReviewedBrowserSubmissionError
):
    pass


@dataclass(frozen=True)
class ReviewedSubmitControl:
    """
    Fresh pre-submit browser evidence.

    This object is descriptive authority only. Possessing it does not
    grant permission to submit; ApplicationSubmissionService owns that
    authority boundary.

    snapshot_fingerprint binds the eventual one-shot activation to the
    exact inspected browser state.
    """

    browser_session_id: str
    page_url: str

    control_ref: str
    control_role: str
    control_name: str

    snapshot_fingerprint: str

    application_review_fingerprint: str

    unique: bool
    enabled: bool

    meta_data: dict[str, object] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class ReviewedSubmitConfirmation:
    """
    Post-activation confirmation evidence.

    confirmed=False is intentionally allowed so the domain transaction
    can leave the application in SUBMITTING and require reconciliation.
    """

    confirmed: bool

    snapshot_fingerprint: str

    confirmation_reference: str | None = None
    page_url: str | None = None

    meta_data: dict[str, object] = field(
        default_factory=dict
    )


class ReviewedSubmissionBrowser(Protocol):
    async def inspect_submit_boundary(
        self,
        *,
        application_id: str,
        tenant_id: str,
        browser_session_id: str,
        expected_review_fingerprint: str,
    ) -> ReviewedSubmitControl:
        """
        Return fresh evidence for exactly one visible submit control.

        Implementations must independently establish that the current
        external form corresponds to expected_review_fingerprint.
        """
        ...

    async def activate_submit_once(
        self,
        *,
        evidence: ReviewedSubmitControl,
    ) -> ReviewedSubmitConfirmation:
        """
        Perform exactly one irreversible submit activation.

        Implementations must fail closed if evidence no longer matches
        the current browser state. They must never silently reacquire a
        different control and must never automatically retry.
        """
        ...


class ReviewedBrowserSubmissionActuator:
    """
    Narrow browser actuator used by ApplicationSubmissionService.

    It has no generic interaction interface. Its complete browser
    authority is:

        inspect one reviewed submit boundary
        -> validate exact evidence
        -> activate that exact boundary once
        -> return confirmation evidence
    """

    def __init__(
        self,
        browser: ReviewedSubmissionBrowser,
    ) -> None:
        self._browser = browser

    @staticmethod
    def _required_text(
        value: str,
        *,
        field_name: str,
    ) -> str:
        value = value.strip()

        if not value:
            raise BrowserSubmissionEvidenceInvalid(
                f"Missing reviewed browser evidence: {field_name}."
            )

        return value

    def _validate_pre_submit(
        self,
        *,
        application: JobApplication,
        expected_review_fingerprint: str,
        evidence: ReviewedSubmitControl,
    ) -> None:
        browser_session_id = self._required_text(
            evidence.browser_session_id,
            field_name="browser_session_id",
        )

        expected_session = self._required_text(
            application.browser_session_id or "",
            field_name="application.browser_session_id",
        )

        if browser_session_id != expected_session:
            raise BrowserSubmissionEvidenceInvalid(
                "Reviewed submit evidence belongs to a different "
                "browser session."
            )

        self._required_text(
            evidence.page_url,
            field_name="page_url",
        )

        self._required_text(
            evidence.control_ref,
            field_name="control_ref",
        )

        role = self._required_text(
            evidence.control_role,
            field_name="control_role",
        ).lower()

        if role != "button":
            raise BrowserSubmissionEvidenceInvalid(
                "Reviewed submit control is not role=button."
            )

        self._required_text(
            evidence.control_name,
            field_name="control_name",
        )

        self._required_text(
            evidence.snapshot_fingerprint,
            field_name="snapshot_fingerprint",
        )

        if not evidence.unique:
            raise BrowserSubmissionEvidenceInvalid(
                "Reviewed submit control is not unique."
            )

        if not evidence.enabled:
            raise BrowserSubmissionEvidenceInvalid(
                "Reviewed submit control is disabled."
            )

        actual_review_fingerprint = self._required_text(
            evidence.application_review_fingerprint,
            field_name="application_review_fingerprint",
        )

        if not hmac.compare_digest(
            actual_review_fingerprint,
            expected_review_fingerprint,
        ):
            raise BrowserSubmissionEvidenceInvalid(
                "Browser form evidence does not match the "
                "approved application review fingerprint."
            )

    def _validate_confirmation(
        self,
        *,
        inspected: ReviewedSubmitControl,
        confirmation: ReviewedSubmitConfirmation,
    ) -> None:
        fingerprint = self._required_text(
            confirmation.snapshot_fingerprint,
            field_name="confirmation.snapshot_fingerprint",
        )

        if not hmac.compare_digest(
            fingerprint,
            inspected.snapshot_fingerprint,
        ):
            raise BrowserSubmissionEvidenceInvalid(
                "Submission confirmation is not bound to the "
                "inspected pre-submit snapshot."
            )

        if confirmation.confirmed:
            self._required_text(
                confirmation.confirmation_reference or "",
                field_name="confirmation_reference",
            )

    async def submit(
        self,
        *,
        application: JobApplication,
    ) -> SubmissionEvidence:
        expected_review_fingerprint = (
            application_review_fingerprint(
                application
            )
        )

        browser_session_id = self._required_text(
            application.browser_session_id or "",
            field_name="application.browser_session_id",
        )

        inspected = (
            await self._browser.inspect_submit_boundary(
                application_id=application.id,
                tenant_id=application.tenant_id,
                browser_session_id=browser_session_id,
                expected_review_fingerprint=(
                    expected_review_fingerprint
                ),
            )
        )

        self._validate_pre_submit(
            application=application,
            expected_review_fingerprint=(
                expected_review_fingerprint
            ),
            evidence=inspected,
        )

        # Exactly one irreversible browser operation is possible here.
        # No retry loop exists.
        confirmation = (
            await self._browser.activate_submit_once(
                evidence=inspected,
            )
        )

        self._validate_confirmation(
            inspected=inspected,
            confirmation=confirmation,
        )

        return SubmissionEvidence(
            confirmed=confirmation.confirmed,
            confirmation_reference=(
                confirmation.confirmation_reference
            ),
            meta_data={
                "browser_submission": {
                    "browser_session_id":
                        inspected.browser_session_id,

                    "page_url":
                        inspected.page_url,

                    "control_ref":
                        inspected.control_ref,

                    "control_role":
                        inspected.control_role,

                    "control_name":
                        inspected.control_name,

                    "pre_submit_snapshot_fingerprint":
                        inspected.snapshot_fingerprint,

                    "post_submit_page_url":
                        confirmation.page_url,

                    "confirmation":
                        dict(
                            confirmation.meta_data
                        ),
                }
            },
        )
