from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, FrozenSet

from project_gideon.models import (
    ApplicationState,
    JobApplication,
)
from project_gideon.ports import ApplicationRepository


class InvalidApplicationTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS: Dict[
    ApplicationState,
    FrozenSet[ApplicationState],
] = {
    ApplicationState.DISCOVERED: frozenset(
        {
            ApplicationState.SHORTLISTED,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.SHORTLISTED: frozenset(
        {
            ApplicationState.PREPARING,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.PREPARING: frozenset(
        {
            ApplicationState.FORM_IN_PROGRESS,
            ApplicationState.NEEDS_INPUT,
            ApplicationState.FAILED,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.FORM_IN_PROGRESS: frozenset(
        {
            ApplicationState.NEEDS_INPUT,
            ApplicationState.READY_FOR_REVIEW,
            ApplicationState.FAILED,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.NEEDS_INPUT: frozenset(
        {
            ApplicationState.FORM_IN_PROGRESS,
            ApplicationState.READY_FOR_REVIEW,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.READY_FOR_REVIEW: frozenset(
        {
            ApplicationState.APPROVED,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.APPROVED: frozenset(
        {
            ApplicationState.SUBMITTED,
            ApplicationState.FAILED,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.SUBMITTED: frozenset(
        {
            ApplicationState.WITHDRAWN,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.FAILED: frozenset(
        {
            ApplicationState.PREPARING,
            ApplicationState.FORM_IN_PROGRESS,
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.WITHDRAWN: frozenset(
        {
            ApplicationState.CLOSED,
        }
    ),
    ApplicationState.CLOSED: frozenset(),
}


class ApplicationLifecycleService:
    """
    Deterministic owner of JobApplication state transitions.

    Agents may request transitions, but they do not define transition rules.
    """

    def __init__(
        self,
        repository: ApplicationRepository,
    ) -> None:
        self._repository = repository

    @staticmethod
    def can_transition(
        current: ApplicationState,
        target: ApplicationState,
    ) -> bool:
        return target in _ALLOWED_TRANSITIONS[current]

    async def claim_transition(
        self,
        *,
        application_id: str,
        tenant_id: str,
        target: ApplicationState,
    ) -> JobApplication:
        """
        Atomically claim a lifecycle transition.

        Intended for transitions which guard irreversible external
        side effects. Exactly one concurrent caller may move the
        application away from the observed source state.
        """

        application = await self._repository.get(
            application_id,
            tenant_id,
        )

        if not self.can_transition(
            application.state,
            target,
        ):
            raise InvalidApplicationTransition(
                f"Illegal application transition: "
                f"{application.state.value} -> {target.value}"
            )

        now = datetime.now(timezone.utc)

        update = {
            "state": target,
            "updated_at": now,
        }

        if target is ApplicationState.SUBMITTED:
            update["submitted_at"] = now

        candidate = application.model_copy(
            update=update,
        )

        claimed = await self._repository.claim_state(
            candidate,
            expected_state=application.state,
        )

        if claimed is None:
            current = await self._repository.get(
                application_id,
                tenant_id,
            )

            raise InvalidApplicationTransition(
                "Application state changed concurrently: "
                f"expected {application.state.value}, "
                f"found {current.state.value}."
            )

        return claimed
    async def transition(
        self,
        *,
        application_id: str,
        tenant_id: str,
        target: ApplicationState,
    ) -> JobApplication:
        application = await self._repository.get(
            application_id,
            tenant_id,
        )

        if not self.can_transition(
            application.state,
            target,
        ):
            raise InvalidApplicationTransition(
                f"Illegal application transition: "
                f"{application.state.value} -> {target.value}"
            )

        now = datetime.now(timezone.utc)

        update = {
            "state": target,
            "updated_at": now,
        }

        if target is ApplicationState.SUBMITTED:
            update["submitted_at"] = now

        updated = application.model_copy(
            update=update,
        )

        return await self._repository.save(updated)
