from __future__ import annotations

from typing import Protocol

from project_gideon.models import (
    BrowserAction,
    BrowserActionResult,
    BrowserSession,
    BrowserSnapshot,
)


class PlaywrightPort(Protocol):
    """
    Gideon's browser-automation boundary.

    The domain layer knows nothing about MCP, Playwright transport,
    Chromium processes, or remote browser infrastructure.
    """

    async def create_session(
        self,
        *,
        tenant_id: str,
        application_id: str,
        url: str,
    ) -> BrowserSession:
        ...

    async def inspect(
        self,
        session_id: str,
    ) -> BrowserSnapshot:
        ...

    async def execute(
        self,
        action: BrowserAction,
    ) -> BrowserActionResult:
        ...

    async def close_session(
        self,
        session_id: str,
    ) -> None:
        ...