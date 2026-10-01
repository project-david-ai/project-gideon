from types import SimpleNamespace

import pytest

from project_gideon.integrations.project_david.mcp_registry import (
    GideonMcpRegistry,
    McpReconciliationError,
)


class FakeHttpUrl:
    """
    Minimal stand-in for a typed URL object returned by a validation model.
    """

    def __init__(self, value: str):
        self._value = value

    def __str__(self) -> str:
        return self._value


class FakeMcpClient:
    def __init__(self, servers=None):
        self.servers = list(servers or [])
        self.created = []
        self.updated = []

    def list_servers(self):
        return list(self.servers)

    def create_server(
        self,
        *,
        name,
        url,
    ):
        server = SimpleNamespace(
            id="mcpreg_created",
            name=name,
            url=FakeHttpUrl(url),
        )

        self.servers.append(server)
        self.created.append(
            {
                "name": name,
                "url": url,
            }
        )

        return server

    def update_server(
        self,
        server_id,
        *,
        name=None,
        timeout_seconds=None,
        enabled=None,
    ):
        self.updated.append(
            {
                "server_id": server_id,
                "name": name,
                "timeout_seconds": timeout_seconds,
                "enabled": enabled,
            }
        )

        raise AssertionError(
            "ensure_server must not mutate an MCP registration URL."
        )

    def discover_tools(self, server):
        return []

    def list_assistant_tools(self, assistant_id):
        return []

    def attach_tools(
        self,
        *,
        assistant_id,
        tools,
    ):
        raise NotImplementedError

    def detach_assistant_tools(
        self,
        assistant_id,
        *,
        server_id,
        tools,
    ):
        raise NotImplementedError


def test_typed_url_equal_to_string_is_reused():
    server = SimpleNamespace(
        id="mcpreg_existing",
        name="playwright-primary",
        url=FakeHttpUrl(
            "http://playwright-mcp:8931/mcp"
        ),
    )

    client = FakeMcpClient(
        servers=[server]
    )

    registry = GideonMcpRegistry(client)

    resolved = registry.ensure_server(
        name="playwright-primary",
        url="http://playwright-mcp:8931/mcp",
    )

    assert resolved is server
    assert client.created == []
    assert client.updated == []


def test_trailing_slash_does_not_change_identity():
    server = SimpleNamespace(
        id="mcpreg_existing",
        name="playwright-primary",
        url=FakeHttpUrl(
            "http://playwright-mcp:8931/mcp/"
        ),
    )

    client = FakeMcpClient(
        servers=[server]
    )

    registry = GideonMcpRegistry(client)

    resolved = registry.ensure_server(
        name="playwright-primary",
        url="http://playwright-mcp:8931/mcp",
    )

    assert resolved is server
    assert client.updated == []


def test_genuinely_different_url_is_not_silently_mutated():
    server = SimpleNamespace(
        id="mcpreg_existing",
        name="playwright-primary",
        url=FakeHttpUrl(
            "http://old-playwright:8931/mcp"
        ),
    )

    client = FakeMcpClient(
        servers=[server]
    )

    registry = GideonMcpRegistry(client)

    with pytest.raises(
        McpReconciliationError,
        match="different remote URL",
    ):
        registry.ensure_server(
            name="playwright-primary",
            url="http://playwright-mcp:8931/mcp",
        )

    assert client.created == []
    assert client.updated == []