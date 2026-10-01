from types import SimpleNamespace

import pytest

from project_gideon.integrations.project_david import (
    AssistantReconciliationError,
    GideonAssistantRegistry,
    GideonMcpRegistry,
    ProjectDavidBootstrap,
    ProjectDavidConfig,
)


class FakeAssistantsClient:
    def __init__(self):
        self.records = []
        self.created = []
        self.updated = []

    def list_assistants(self):
        return list(self.records)

    def create_assistant(self, **kwargs):
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
            setattr(assistant, key, value)

        self.updated.append(
            {
                "assistant_id": assistant_id,
                **updates,
            }
        )

        return assistant


class FakeToolCollection:
    def __init__(self):
        self.discovered = True


class FakeMcpClient:
    def __init__(self):
        self.servers = []
        self.created = []
        self.updated = []
        self.discovery_count = 0
        self.attach_count = 0

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
        server = next(
            item
            for item in self.servers
            if item.id == server_id
        )

        for key, value in updates.items():
            setattr(server, key, value)

        self.updated.append(
            {
                "server_id": server_id,
                **updates,
            }
        )

        return server

    def discover_tools(self, server):
        self.discovery_count += 1
        return FakeToolCollection()

    def list_assistant_tools(self, assistant_id):
        return []

    def attach_tools(
        self,
        *,
        assistant_id,
        tools,
    ):
        self.attach_count += 1

    def detach_assistant_tools(
        self,
        assistant_id,
        *,
        server_id,
        tools,
    ):
        raise AssertionError(
            "No detach should occur in bootstrap foundation test."
        )


class FakeEntity:
    def __init__(self):
        self.assistants = FakeAssistantsClient()
        self.mcp = FakeMcpClient()


def make_config():
    return ProjectDavidConfig(
        base_url="http://project-david",
        api_key="test-key",
        assistant_name="gideon-supervisor",
        assistant_model="test/model",
        playwright_mcp_name="playwright-primary",
        playwright_mcp_url="http://playwright-mcp/mcp",
    )


def test_assistant_is_created_when_missing():
    client = FakeAssistantsClient()

    registry = GideonAssistantRegistry(client)

    assistant = registry.ensure_supervisor(
        name="gideon-supervisor",
        model="test/model",
    )

    assert assistant.id == "assistant_1"
    assert len(client.created) == 1


def test_assistant_reconciliation_is_idempotent():
    client = FakeAssistantsClient()

    registry = GideonAssistantRegistry(client)

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

    registry = GideonAssistantRegistry(client)

    with pytest.raises(
        AssistantReconciliationError,
        match="Multiple",
    ):
        registry.ensure_supervisor(
            name="gideon-supervisor",
            model="test/model",
        )


def test_mcp_server_is_created_when_missing():
    client = FakeMcpClient()

    registry = GideonMcpRegistry(client)

    server = registry.ensure_server(
        name="playwright-primary",
        url="http://playwright/mcp",
    )

    assert server.id == "mcp_server_1"
    assert len(client.created) == 1


def test_mcp_server_is_reused_when_matching():
    client = FakeMcpClient()

    registry = GideonMcpRegistry(client)

    first = registry.ensure_server(
        name="playwright-primary",
        url="http://playwright/mcp",
    )

    second = registry.ensure_server(
        name="playwright-primary",
        url="http://playwright/mcp",
    )

    assert second.id == first.id
    assert len(client.created) == 1


def test_bootstrap_discovers_but_does_not_attach_tools():
    entity = FakeEntity()

    bootstrap = ProjectDavidBootstrap(
        client=entity,
        config=make_config(),
    )

    bindings = bootstrap.reconcile()

    assert bindings.assistant_id == "assistant_1"
    assert bindings.mcp_server_id == "mcp_server_1"

    assert entity.mcp.discovery_count == 1

    # Critical security property:
    # MCP discovery alone never grants capabilities.
    assert entity.mcp.attach_count == 0


def test_bootstrap_is_idempotent():
    entity = FakeEntity()

    bootstrap = ProjectDavidBootstrap(
        client=entity,
        config=make_config(),
    )

    first = bootstrap.reconcile()
    second = bootstrap.reconcile()

    assert second.assistant_id == first.assistant_id
    assert second.mcp_server_id == first.mcp_server_id

    assert len(entity.assistants.created) == 1
    assert len(entity.mcp.created) == 1