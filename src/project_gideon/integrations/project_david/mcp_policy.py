from __future__ import annotations

from typing import Any


class PlaywrightCapabilityPolicyError(RuntimeError):
    """The live Playwright MCP surface cannot satisfy Gideon's policy."""


# Explicit remote capabilities approved for Gideon's preparation phase.
#
# Discovery is descriptive. Attachment is authoritative.
#
# New tools advertised by the MCP server are never granted automatically.
PLAYWRIGHT_PREPARATION_TOOL_NAMES: tuple[str, ...] = (
    "browser_navigate",
    "browser_navigate_back",
    "browser_snapshot",
    "browser_find",
    "browser_fill_form",
    "browser_select_option",
    "browser_file_upload",
    "browser_wait_for",
    "browser_take_screenshot",
)


# Explicitly authority-expanding capabilities which preparation must not gain.
PLAYWRIGHT_FORBIDDEN_PREPARATION_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "browser_click",
        "browser_press_key",
        "browser_type",
        "browser_evaluate",
        "browser_run_code_unsafe",
        "browser_handle_dialog",
    }
)


def select_playwright_preparation_tools(
    discovered_tools: Any,
) -> Any:
    """
    Validate the live MCP surface and select Gideon's approved subset.

    The returned collection consists of the original discovered MCP tool
    objects so Project David retains their server provenance.
    """

    discovered_names = set(
        discovered_tools.names()
    )

    required_names = set(
        PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )

    missing = sorted(
        required_names - discovered_names
    )

    if missing:
        raise PlaywrightCapabilityPolicyError(
            "Playwright MCP is missing required Gideon preparation tools: "
            + ", ".join(missing)
        )

    selected = discovered_tools.select(
        *PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )

    selected_names = set(
        selected.names()
    )

    forbidden = sorted(
        selected_names
        & PLAYWRIGHT_FORBIDDEN_PREPARATION_TOOL_NAMES
    )

    if forbidden:
        raise PlaywrightCapabilityPolicyError(
            "Forbidden Playwright tools entered preparation authority: "
            + ", ".join(forbidden)
        )

    return selected