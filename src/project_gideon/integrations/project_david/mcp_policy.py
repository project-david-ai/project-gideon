from __future__ import annotations

from typing import FrozenSet


# These are Gideon's semantic browser capabilities.
#
# They are NOT assumed to be the remote Playwright MCP tool names.
# The Project David bootstrap layer must first discover the real tool
# surface and then reconcile an explicit mapping.
PLAYWRIGHT_REQUIRED_CAPABILITIES: FrozenSet[str] = frozenset(
    {
        "navigate",
        "inspect",
        "fill",
        "select",
        "upload",
        "scroll",
        "wait",
        "back",
    }
)


# Generic click remains intentionally outside preparation authority.
PLAYWRIGHT_FORBIDDEN_PREPARATION_CAPABILITIES: FrozenSet[str] = frozenset(
    {
        "generic_click",
        "submit",
    }
)