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
        assistant_id: str,
        *,
        tools: Sequence[Any],
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


def _normalise_url(
    value: object,
) -> str:
    """
    Normalise SDK/Pydantic URL values for registration identity comparison.
    """

    return str(value).strip().rstrip("/")


def _attachment_belongs_to_server(
    attachment: Any,
    server: Any,
) -> bool:
    """
    Determine whether a durable MCP attachment belongs to this registration.

    Prefer explicit server identifiers when the SDK model exposes them.
    Fall back to provider_name for compatibility with attachment models that
    expose provider provenance by logical MCP registration name.
    """

    server_id = str(
        getattr(
            server,
            "id",
            "",
        )
    )

    for attribute in (
        "registration_id",
        "server_id",
        "mcp_server_id",
        "provider_id",
    ):
        value = getattr(
            attachment,
            attribute,
            None,
        )

        if value is not None:
            return str(value) == server_id

    provider_name = getattr(
        attachment,
        "provider_name",
        None,
    )

    server_name = getattr(
        server,
        "name",
        None,
    )

    if provider_name is None:
        return False

    return str(provider_name) in {
        str(server_id),
        str(server_name),
    }


class GideonMcpRegistry:
    """
    Reconcile Gideon's logical MCP composition against Project David.

    Gideon knows only the Project David API contract. It has no knowledge of
    Project David's deployment topology or internal network architecture.

    Discovery never grants authority.

    Attachment reconciliation is scoped to one MCP registration so unrelated
    providers attached to the same assistant remain untouched.
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
            if getattr(
                server,
                "name",
                None,
            ) == name
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
            getattr(
                server,
                "url",
                "",
            )
        )

        desired_url = _normalise_url(
            url
        )

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
        return self._mcp.discover_tools(
            server
        )

    def reconcile_assistant_tools(
        self,
        *,
        assistant_id: str,
        server: Any,
        desired_tools: Sequence[Any],
    ) -> Sequence[Any]:
        """
        Make this registration's durable attachments equal desired_tools.

        Other MCP registrations attached to the assistant are untouched.
        """

        desired = list(
            desired_tools
        )

        if not desired:
            raise McpReconciliationError(
                "Desired MCP tool collection must not be empty."
            )

        foreign = [
            tool
            for tool in desired
            if str(
                getattr(
                    tool,
                    "server_id",
                    "",
                )
            ) != str(server.id)
        ]

        if foreign:
            raise McpReconciliationError(
                "Desired MCP tools contain provenance from another server."
            )

        desired_names = [
            tool.remote_name
            for tool in desired
        ]

        if len(desired_names) != len(set(desired_names)):
            raise McpReconciliationError(
                "Desired MCP tool collection contains duplicate names."
            )

        desired_name_set = set(
            desired_names
        )

        existing = list(
            self._mcp.list_assistant_tools(
                assistant_id
            )
        )

        relevant_existing = [
            tool
            for tool in existing
            if _attachment_belongs_to_server(
                tool,
                server,
            )
        ]

        existing_names = {
            tool.remote_name
            for tool in relevant_existing
        }

        stale_names = sorted(
            existing_names - desired_name_set
        )

        if stale_names:
            self._mcp.detach_assistant_tools(
                assistant_id,
                server_id=server.id,
                tools=stale_names,
            )

        missing = [
            tool
            for tool in desired
            if tool.remote_name not in existing_names
        ]

        if missing:
            self._mcp.attach_tools(
                assistant_id,
                tools=missing,
            )

        final_state = list(
            self._mcp.list_assistant_tools(
                assistant_id
            )
        )

        final_relevant = [
            tool
            for tool in final_state
            if _attachment_belongs_to_server(
                tool,
                server,
            )
        ]

        final_names = {
            tool.remote_name
            for tool in final_relevant
        }

        if final_names != desired_name_set:
            raise McpReconciliationError(
                "MCP attachment reconciliation postcondition failed: "
                f"expected={sorted(desired_name_set)!r}, "
                f"actual={sorted(final_names)!r}."
            )

        return final_state