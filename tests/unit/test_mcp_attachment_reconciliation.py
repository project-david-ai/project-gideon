from types import SimpleNamespace

from project_gideon.integrations.project_david.mcp_registry import (
    GideonMcpRegistry,
)


def tool(
    name,
    server_id="server-1",
):
    return SimpleNamespace(
        name=name,
        remote_name=name,
        server_id=server_id,
    )


class FakeMcp:
    def __init__(self):
        self.attached = []
        self.attach_calls = []
        self.detach_calls = []

    def list_assistant_tools(
        self,
        assistant_id,
    ):
        return list(
            self.attached
        )

    def attach_tools(
        self,
        assistant_id,
        *,
        tools,
    ):
        tools = list(tools)

        self.attach_calls.append(
            [
                item.remote_name
                for item in tools
            ]
        )

        self.attached.extend(
            tools
        )

    def detach_assistant_tools(
        self,
        assistant_id,
        *,
        server_id,
        tools,
    ):
        self.detach_calls.append(
            list(tools)
        )

        self.attached = [
            item
            for item in self.attached
            if not (
                item.server_id == server_id
                and item.remote_name in tools
            )
        ]


def test_missing_tools_are_attached():
    client = FakeMcp()
    registry = GideonMcpRegistry(client)

    server = SimpleNamespace(
        id="server-1",
        name="playwright-primary",
    )

    registry.reconcile_assistant_tools(
        assistant_id="assistant-1",
        server=server,
        desired_tools=[
            tool("browser_navigate"),
            tool("browser_snapshot"),
        ],
    )

    assert client.attach_calls == [
        [
            "browser_navigate",
            "browser_snapshot",
        ]
    ]


def test_matching_attachment_state_is_noop():
    client = FakeMcp()

    client.attached = [
        tool("browser_navigate"),
        tool("browser_snapshot"),
    ]

    registry = GideonMcpRegistry(client)

    server = SimpleNamespace(
        id="server-1",
        name="playwright-primary",
    )

    registry.reconcile_assistant_tools(
        assistant_id="assistant-1",
        server=server,
        desired_tools=[
            tool("browser_navigate"),
            tool("browser_snapshot"),
        ],
    )

    assert client.attach_calls == []
    assert client.detach_calls == []


def test_other_mcp_provider_is_preserved():
    client = FakeMcp()

    client.attached = [
        tool(
            "stale-playwright-tool",
            "server-1",
        ),
        tool(
            "foreign-tool",
            "server-2",
        ),
    ]

    registry = GideonMcpRegistry(client)

    server = SimpleNamespace(
        id="server-1",
        name="playwright-primary",
    )

    final_state = registry.reconcile_assistant_tools(
        assistant_id="assistant-1",
        server=server,
        desired_tools=[
            tool(
                "browser_navigate",
                "server-1",
            ),
        ],
    )

    assert client.detach_calls == [
        ["stale-playwright-tool"]
    ]

    assert {
        (
            item.server_id,
            item.remote_name,
        )
        for item in final_state
    } == {
        (
            "server-1",
            "browser_navigate",
        ),
        (
            "server-2",
            "foreign-tool",
        ),
    }

def test_registration_id_identifies_real_project_david_attachment_shape():
    client = FakeMcp()

    client.attached = [
        SimpleNamespace(
            remote_name="browser_navigate",
            registration_id="server-1",
            provider_name="playwright-primary__browser_navigate",
        )
    ]

    registry = GideonMcpRegistry(
        client
    )

    server = SimpleNamespace(
        id="server-1",
        name="playwright-primary",
    )

    final_state = registry.reconcile_assistant_tools(
        assistant_id="assistant-1",
        server=server,
        desired_tools=[
            tool(
                "browser_navigate",
                "server-1",
            ),
        ],
    )

    assert len(final_state) == 1
    assert client.attach_calls == []
    assert client.detach_calls == []
