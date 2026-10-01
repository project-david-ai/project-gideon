from __future__ import annotations

from typing import Any, Protocol, Sequence


class McpClientProtocol(Protocol):
    def list_servers(self) -> Sequence[Any]:
        ...

    def create_server(
        self,
        *,
        name: str,
        url: str,
    ) -> Any:
        ...

    def update_server(
        self,
        server_id: str,
        *,
        name: str | None = None,
        timeout_seconds: float | None = None,
        enabled: bool | None = None,
    ) -> Any:
        ...

    def discover_tools(
        self,
        server: Any,
    ) -> Any:
        ...

    def list_assistant_tools(
        self,
        assistant_id: str,
    ) -> Sequence[Any]:
        ...

    def attach_tools(
        self,
        *,
        assistant_id: str,
        tools: Any,
    ) -> Any:
        ...

    def detach_assistant_tools(
        self,
        assistant_id: str,
        *,
        server_id: str,
        tools: list[str],
    ) -> Any:
        ...


class McpReconciliationError(RuntimeError):
    pass


def _normalise_url(value: object) -> str:
    """
    Normalise SDK/Pydantic URL values for identity comparison.

    Project David returns typed URL values from registration models,
    while Gideon's desired configuration originates as plain strings.
    """

    return str(value).strip().rstrip("/")


class GideonMcpRegistry:
    """
    Own Project David MCP server registration and tool attachment
    reconciliation.

    Discovery never implies attachment.

    The remote MCP URL is treated as registration identity. Project David
    allows mutable registration properties such as name, timeout and enabled
    state, but Gideon does not attempt to mutate a registration URL in place.
    """

    def __init__(
        self,
        mcp: McpClientProtocol,
    ) -> None:
        self._mcp = mcp

    def ensure_server(
        self,
        *,
        name: str,
        url: str,
    ) -> Any:
        matches = [
            server
            for server in self._mcp.list_servers()
            if getattr(server, "name", None) == name
        ]

        if len(matches) > 1:
            raise McpReconciliationError(
                f"Multiple MCP servers exist with logical name={name!r}."
            )

        if not matches:
            return self._mcp.create_server(
                name=name,
                url=url,
            )

        server = matches[0]

        current_url = _normalise_url(
            getattr(server, "url", "")
        )

        desired_url = _normalise_url(url)

        if current_url != desired_url:
            raise McpReconciliationError(
                "Existing Project David MCP registration has a different "
                f"remote URL for logical name={name!r}: "
                f"current={current_url!r}, desired={desired_url!r}. "
                "Registration URL changes require an explicit replacement "
                "workflow."
            )

        return server

    def discover(
        self,
        server: Any,
    ) -> Any:
        return self._mcp.discover_tools(server)