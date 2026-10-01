from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from project_gideon.models import (
    BrowserAction,
    BrowserActionResult,
    BrowserSession,
    BrowserSessionState,
    BrowserSnapshot,
)


class FakePlaywrightAdapter:
    """
    Deterministic PlaywrightPort implementation for unit tests.

    No browser, MCP server, or Project David runtime is involved.
    """

    def __init__(
        self,
        snapshot: BrowserSnapshot,
    ) -> None:
        self._snapshot = snapshot
        self.actions: List[BrowserAction] = []
        self.session: Optional[BrowserSession] = None

    async def create_session(
        self,
        *,
        tenant_id: str,
        application_id: str,
        url: str,
    ) -> BrowserSession:
        self.session = BrowserSession(
            id=f"browser_{uuid4().hex}",
            tenant_id=tenant_id,
            application_id=application_id,
            state=BrowserSessionState.ACTIVE,
            current_url=url,
        )

        self._snapshot = self._snapshot.model_copy(
            update={
                "session_id": self.session.id,
                "url": url,
            }
        )

        return self.session

    async def inspect(
        self,
        session_id: str,
    ) -> BrowserSnapshot:
        if self.session is None:
            raise RuntimeError("Browser session has not been created.")

        if self.session.id != session_id:
            raise KeyError(
                f"Unknown browser session: {session_id}"
            )

        return self._snapshot

    async def execute(
        self,
        action: BrowserAction,
    ) -> BrowserActionResult:
        if self.session is None:
            raise RuntimeError("Browser session has not been created.")

        if self.session.id != action.session_id:
            raise KeyError(
                f"Unknown browser session: {action.session_id}"
            )

        self.actions.append(action)

        return BrowserActionResult(
            success=True,
            session_id=action.session_id,
            action=action.action,
            message="Fake browser action completed.",
            snapshot=self._snapshot,
        )

    async def close_session(
        self,
        session_id: str,
    ) -> None:
        if self.session is None:
            return

        if self.session.id != session_id:
            raise KeyError(
                f"Unknown browser session: {session_id}"
            )

        self.session = self.session.model_copy(
            update={
                "state": BrowserSessionState.CLOSED,
            }
        )