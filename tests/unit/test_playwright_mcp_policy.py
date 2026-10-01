from types import SimpleNamespace

import pytest

from project_gideon.integrations.project_david.mcp_policy import (
    PLAYWRIGHT_FORBIDDEN_PREPARATION_TOOL_NAMES,
    PLAYWRIGHT_PREPARATION_TOOL_NAMES,
    PlaywrightCapabilityPolicyError,
    select_playwright_preparation_tools,
)


class FakeCollection:
    def __init__(self, names):
        self._tools = [
            SimpleNamespace(
                name=name,
                remote_name=name,
            )
            for name in names
        ]

    def names(self):
        return [
            tool.remote_name
            for tool in self._tools
        ]

    def select(self, *names):
        by_name = {
            tool.remote_name: tool
            for tool in self._tools
        }

        selected = FakeCollection([])

        selected._tools = [
            by_name[name]
            for name in names
        ]

        return selected


def test_policy_is_explicit_allowlist():
    assert PLAYWRIGHT_PREPARATION_TOOL_NAMES == (
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


def test_policy_excludes_authority_expanding_tools():
    assert not (
        set(
            PLAYWRIGHT_PREPARATION_TOOL_NAMES
        )
        & PLAYWRIGHT_FORBIDDEN_PREPARATION_TOOL_NAMES
    )


def test_missing_required_tool_fails_readiness():
    names = list(
        PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )

    names.remove(
        "browser_snapshot"
    )

    with pytest.raises(
        PlaywrightCapabilityPolicyError,
        match="browser_snapshot",
    ):
        select_playwright_preparation_tools(
            FakeCollection(names)
        )


def test_extra_discovered_tools_are_not_granted():
    names = list(
        PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )

    names.extend(
        [
            "browser_click",
            "browser_run_code_unsafe",
        ]
    )

    selected = select_playwright_preparation_tools(
        FakeCollection(names)
    )

    assert selected.names() == list(
        PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )