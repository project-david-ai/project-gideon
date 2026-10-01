from types import SimpleNamespace

import pytest

from project_gideon.integrations.project_david import (
    AssistantReconciliationError,
    GideonAssistantRegistry,
    GideonMcpRegistry,
    ProjectDavidBootstrap,
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.mcp_policy import (
    PLAYWRIGHT_PREPARATION_TOOL_NAMES,
)


class FakeAssistantsClient:
    def __init__(self):
        self.records = []
        self.created = []
        self.updated = []

    def list_assistants(self):
        return list(self.records)

    def create_assistant(
        self,
        **kwargs,
    ):
        assistant = SimpleNamespace(
            id=f"assistant_{len(self.records) + 1}",
            **kwargs,
        )

        self.records.append(assistant)
        self.created.append(kwargs)

        return assistant

    def update_assistant(
        self,
        assistant_id,
        **updates,
    ):
        assistant = next(
            item
            for item in self.records
            if item.id == assistant_id
        )

        for key, value in updates.items():
            setattr(
                assistant,
                key,
                value,
            )

        self.updated.append(
            {
                "assistant_id": assistant_id,
                **updates,
            }
        )

        return assistant


class FakeToolCollection:
    def __init__(
        self,
        tools,
    ):
        self._tools = list(tools)

    def __iter__(self):
        return iter(self._tools)

    def __len__(self):
        return len(self._tools)

    def names(self):
        return [
            tool.remote_name
            for tool in self._tools
        ]

    def select(
        self,
        *names,
    ):
        by_name = {
            tool.remote_name: tool
            for tool in self._tools
        }

        missing = [
            name
            for name in names
            if name not in by_name
        ]

        if missing:
            raise ValueError(
                ", ".join(missing)
            )

        return FakeToolCollection(
            [
                by_name[name]
                for name in names
            ]
        )


class FakeMcpClient:
    def __init__(self):
        self.servers = []
        self.created = []
        self.discovery_count = 0

        self.attached = []
        self.attach_calls = []
        self.detach_calls = []

    def list_servers(self):
        return list(self.servers)

    def create_server(
        self,
        *,
        name,
        url,
    ):
        server = SimpleNamespace(
            id=f"mcp_server_{len(self.servers) + 1}",
            name=name,
            url=url,
        )

        self.servers.append(server)
        self.created.append(server)

        return server

    def update_server(
        self,
        server_id,
        **updates,
    ):
        raise AssertionError(
            "Gideon must not silently mutate MCP registration URL."
        )

    def discover_tools(
        self,
        server,
    ):
        self.discovery_count += 1

        names = list(
            PLAYWRIGHT_PREPARATION_TOOL_NAMES
        )

        # Remote discovery may expose capabilities Gideon does not grant.
        names.extend(
            [
                "browser_click",
                "browser_run_code_unsafe",
            ]
        )

        return FakeToolCollection(
            [
                SimpleNamespace(
                    name=name,
                    remote_name=name,
                    server_id=server.id,
                )
                for name in names
            ]
        )

    def list_assistant_tools(
        self,
        assistant_id,
    ):
        return list(self.attached)

    def attach_tools(
        self,
        assistant_id,
        *,
        tools,
    ):
        tools = list(tools)

        self.attach_calls.append(
            [
                tool.remote_name
                for tool in tools
            ]
        )

        self.attached.extend(tools)

        return list(self.attached)

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
            tool
            for tool in self.attached
            if not (
                tool.server_id == server_id
                and tool.remote_name in tools
            )
        ]


class FakeEntity:
    def __init__(self):
        self.assistants = FakeAssistantsClient()
        self.mcp = FakeMcpClient()


def make_config():
    return ProjectDavidConfig(
        base_url="https://project-david.example",
        api_key="test-key",
        assistant_name="gideon-supervisor",
        assistant_model="test/model",
        playwright_mcp_name="playwright-primary",
        playwright_mcp_url="https://playwright.example/mcp",
    )


def test_assistant_is_created_when_missing():
    client = FakeAssistantsClient()

    registry = GideonAssistantRegistry(
        client
    )

    assistant = registry.ensure_supervisor(
        name="gideon-supervisor",
        model="test/model",
    )

    assert assistant.id == "assistant_1"
    assert len(client.created) == 1


def test_assistant_reconciliation_is_idempotent():
    client = FakeAssistantsClient()

    registry = GideonAssistantRegistry(
        client
    )

    first = registry.ensure_supervisor(
        name="gideon-supervisor",
        model="test/model",
    )

    second = registry.ensure_supervisor(
        name="gideon-supervisor",
        model="test/model",
    )

    assert second.id == first.id
    assert len(client.created) == 1
    assert len(client.updated) == 1


def test_duplicate_logical_assistant_is_rejected():
    client = FakeAssistantsClient()

    client.records = [
        SimpleNamespace(
            id="assistant_1",
            name="gideon-supervisor",
        ),
        SimpleNamespace(
            id="assistant_2",
            name="gideon-supervisor",
        ),
    ]

    registry = GideonAssistantRegistry(
        client
    )

    with pytest.raises(
        AssistantReconciliationError,
        match="Multiple",
    ):
        registry.ensure_supervisor(
            name="gideon-supervisor",
            model="test/model",
        )


def test_mcp_server_is_created_from_configured_endpoint():
    client = FakeMcpClient()

    registry = GideonMcpRegistry(
        client
    )

    server = registry.ensure_server(
        name="playwright-primary",
        url="https://tenant-playwright.example/mcp",
    )

    assert server.id == "mcp_server_1"
    assert server.url == "https://tenant-playwright.example/mcp"
    assert len(client.created) == 1


def test_bootstrap_reconciles_governed_playwright_tools():
    entity = FakeEntity()

    bootstrap = ProjectDavidBootstrap(
        client=entity,
        config=make_config(),
    )

    bindings = bootstrap.reconcile()

    assert bindings.assistant_id == "assistant_1"
    assert bindings.mcp_server_id == "mcp_server_1"

    assert entity.mcp.discovery_count == 1

    assert entity.mcp.attach_calls == [
        list(
            PLAYWRIGHT_PREPARATION_TOOL_NAMES
        )
    ]

    assert {
        tool.remote_name
        for tool in entity.mcp.attached
    } == set(
        PLAYWRIGHT_PREPARATION_TOOL_NAMES
    )

    assert (
        bindings.meta_data[
            "playwright_attached_count"
        ]
        == len(
            PLAYWRIGHT_PREPARATION_TOOL_NAMES
        )
    )


def test_bootstrap_attachment_reconciliation_is_idempotent():
    entity = FakeEntity()

    bootstrap = ProjectDavidBootstrap(
        client=entity,
        config=make_config(),
    )

    first = bootstrap.reconcile()
    second = bootstrap.reconcile()

    assert second.assistant_id == first.assistant_id
    assert second.mcp_server_id == first.mcp_server_id

    assert len(
        entity.assistants.created
    ) == 1

    assert len(
        entity.mcp.created
    ) == 1

    # Only the first reconcile needs to attach anything.
    assert len(
        entity.mcp.attach_calls
    ) == 1

    assert entity.mcp.detach_calls == []

    assert entity.mcp.discovery_count == 2