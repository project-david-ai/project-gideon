from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from project_gideon.integrations.playwright import (
    assert_preparation_action_allowed,
)
from project_gideon.models import (
    ApplicationPackage,
    ApplicationPreparationResult,
    ApplicationState,
    BrowserAction,
    BrowserActionType,
    BrowserControl,
    BrowserControlType,
    UnresolvedQuestion,
)
from project_gideon.ports import (
    ApplicationRepository,
    PlaywrightPort,
)
from project_gideon.services.application_lifecycle import (
    ApplicationLifecycleService,
)


class ApplicationPreparationError(ValueError):
    pass


class BrowserActionFailed(ApplicationPreparationError):
    pass


class ApplicationPreparationService:
    """
    Deterministic application-form preparation workflow.

    Responsibilities:
      - validate package/application identity
      - create or resume the browser session
      - inspect normalized browser controls
      - fill only authoritative known values
      - upload the selected CV where confidently identified
      - surface unknown required questions
      - move the application to NEEDS_INPUT or READY_FOR_REVIEW

    This service has no submission capability.
    """

    def __init__(
        self,
        *,
        applications: ApplicationRepository,
        browser: PlaywrightPort,
    ) -> None:
        self._applications = applications
        self._browser = browser
        self._lifecycle = ApplicationLifecycleService(
            applications
        )

    async def prepare(
        self,
        package: ApplicationPackage,
    ) -> ApplicationPreparationResult:
        tenant_id = package.candidate.tenant_id

        application = await self._applications.get(
            package.application_id,
            tenant_id,
        )

        self._validate_package(
            application=application,
            package=package,
        )

        application = await self._enter_form_workflow(
            application
        )

        if application.browser_session_id is None:
            session = await self._browser.create_session(
                tenant_id=tenant_id,
                application_id=application.id,
                url=package.application_url,
            )

            application = application.model_copy(
                update={
                    "browser_session_id": session.id,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

            application = await self._applications.save(
                application
            )

        session_id = application.browser_session_id

        if session_id is None:
            raise ApplicationPreparationError(
                "Browser session was not established."
            )

        snapshot = await self._browser.inspect(
            session_id
        )

        actions: List[BrowserAction] = []
        unresolved: List[UnresolvedQuestion] = []

        for control in snapshot.controls:
            if control.disabled:
                continue

            action = self._action_for_control(
                control=control,
                package=package,
                session_id=session_id,
            )

            if action is not None:
                assert_preparation_action_allowed(action)

                result = await self._browser.execute(action)

                if not result.success:
                    raise BrowserActionFailed(
                        result.message
                        or (
                            "Browser action failed: "
                            f"{action.action.value}"
                        )
                    )

                actions.append(action)
                continue

            question = self._unresolved_for_control(
                control
            )

            if question is not None:
                unresolved.append(question)

        snapshot = await self._browser.inspect(
            session_id
        )

        application = application.model_copy(
            update={
                "unresolved_questions": unresolved,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        application = await self._applications.save(
            application
        )

        target = (
            ApplicationState.NEEDS_INPUT
            if unresolved
            else ApplicationState.READY_FOR_REVIEW
        )

        application = await self._lifecycle.transition(
            application_id=application.id,
            tenant_id=application.tenant_id,
            target=target,
        )

        return ApplicationPreparationResult(
            application=application,
            snapshot=snapshot,
            actions=actions,
            unresolved_questions=unresolved,
        )

    async def _enter_form_workflow(
        self,
        application,
    ):
        if application.state is ApplicationState.PREPARING:
            return await self._lifecycle.transition(
                application_id=application.id,
                tenant_id=application.tenant_id,
                target=ApplicationState.FORM_IN_PROGRESS,
            )

        if application.state is ApplicationState.NEEDS_INPUT:
            return await self._lifecycle.transition(
                application_id=application.id,
                tenant_id=application.tenant_id,
                target=ApplicationState.FORM_IN_PROGRESS,
            )

        if application.state is ApplicationState.FORM_IN_PROGRESS:
            return application

        raise ApplicationPreparationError(
            "Application cannot enter form preparation from "
            f"state={application.state.value}"
        )

    @staticmethod
    def _validate_package(
        *,
        application,
        package: ApplicationPackage,
    ) -> None:
        if application.id != package.application_id:
            raise ApplicationPreparationError(
                "Application package ID mismatch."
            )

        if application.job_id != package.job_id:
            raise ApplicationPreparationError(
                "Application package job mismatch."
            )

        if application.candidate_id != package.candidate.id:
            raise ApplicationPreparationError(
                "Application package candidate mismatch."
            )

        if (
            application.tenant_id
            != package.candidate.tenant_id
        ):
            raise ApplicationPreparationError(
                "Application package tenant mismatch."
            )

    @staticmethod
    def _action_for_control(
        *,
        control: BrowserControl,
        package: ApplicationPackage,
        session_id: str,
    ) -> BrowserAction | None:
        if control.control_type in {
            BrowserControlType.BUTTON,
            BrowserControlType.LINK,
            BrowserControlType.OTHER,
        }:
            return None

        if (
            control.control_type
            is BrowserControlType.FILE_INPUT
        ):
            identity = " ".join(
                value
                for value in (
                    control.label,
                    control.name,
                )
                if value
            ).lower()

            if any(
                token in identity
                for token in (
                    "cv",
                    "resume",
                    "résumé",
                    "curriculum",
                )
            ):
                return BrowserAction(
                    action=BrowserActionType.UPLOAD,
                    session_id=session_id,
                    control_id=control.id,
                    file_id=package.cv_file_id,
                )

            return None

        if control.id not in package.answers:
            return None

        answer = package.answers[control.id]

        if control.control_type in {
            BrowserControlType.TEXTBOX,
            BrowserControlType.TEXTAREA,
        }:
            return BrowserAction(
                action=BrowserActionType.FILL,
                session_id=session_id,
                control_id=control.id,
                value=str(answer),
            )

        if (
            control.control_type
            is BrowserControlType.COMBOBOX
        ):
            return BrowserAction(
                action=BrowserActionType.SELECT,
                session_id=session_id,
                control_id=control.id,
                value=str(answer),
            )

        # Checkbox and radio controls are intentionally not converted into
        # generic CLICK operations during preparation. Their eventual safe
        # interaction semantics will be reconciled with the real Playwright
        # MCP tool surface during Project David composition.
        return None

    @staticmethod
    def _unresolved_for_control(
        control: BrowserControl,
    ) -> UnresolvedQuestion | None:
        if not control.required:
            return None

        if control.control_type in {
            BrowserControlType.BUTTON,
            BrowserControlType.LINK,
        }:
            return None

        label = (
            control.label
            or control.name
            or control.id
        )

        return UnresolvedQuestion(
            field_id=control.id,
            question=label,
            reason=(
                "Required application field has no authoritative "
                "prepared answer or no safe preparation action."
            ),
            required=True,
            options=control.options,
        )