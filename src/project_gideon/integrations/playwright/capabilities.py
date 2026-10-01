from __future__ import annotations

from typing import FrozenSet

from project_gideon.models import (
    BrowserAction,
    BrowserActionType,
)


class BrowserCapabilityDenied(ValueError):
    pass


PREPARATION_ALLOWED_ACTIONS: FrozenSet[BrowserActionType] = frozenset(
    {
        BrowserActionType.NAVIGATE,
        BrowserActionType.FILL,
        BrowserActionType.SELECT,
        BrowserActionType.UPLOAD,
        BrowserActionType.SCROLL,
        BrowserActionType.WAIT,
        BrowserActionType.BACK,
    }
)


def assert_preparation_action_allowed(
    action: BrowserAction,
) -> None:
    """
    Enforce Gideon's preparation-time browser capability boundary.

    CLICK is intentionally absent.

    A generic browser click may activate a consequential control such as
    Submit. Preparation therefore cannot acquire generic click authority.

    The eventual Project David MCP integration must reconcile this policy
    against tools actually returned by discover_tools(); this module does
    not assume remote MCP tool names.
    """

    if action.action not in PREPARATION_ALLOWED_ACTIONS:
        raise BrowserCapabilityDenied(
            f"Browser action is not permitted during preparation: "
            f"{action.action.value}"
        )