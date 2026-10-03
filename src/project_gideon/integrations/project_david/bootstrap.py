from __future__ import annotations

from project_gideon.integrations.project_david.assistants import (
    GideonAssistantRegistry,
)
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.mcp_policy import (
    select_playwright_preparation_tools,
)
from project_gideon.integrations.project_david.mcp_registry import (
    GideonMcpRegistry,
    _attachment_belongs_to_server,
)
from project_gideon.models import (
    ProjectDavidRuntimeBindings,
)


class ProjectDavidBootstrap:
    """
    Reconcile Gideon's composition against the Project David API.

    Readiness requires:

    - the logical Gideon supervisor exists;
    - the configured Playwright MCP registration exists;
    - live MCP discovery succeeds;
    - Gideon's explicit capability policy can be satisfied;
    - durable assistant attachments match that policy.

    Project David deployment and network topology are intentionally outside
    Gideon's responsibility.
    """

    def __init__(
        self,
        *,
        client,
        config: ProjectDavidConfig,
    ) -> None:
        self._client = client
        self._config = config

    def reconcile(
        self,
    ) -> ProjectDavidRuntimeBindings:
        vector_store_id = (
            self._client.vectors.get_or_create_file_search_store()
        )

        assistant_registry = GideonAssistantRegistry(
            self._client.assistants
        )

        assistant = assistant_registry.ensure_supervisor(
            name=self._config.assistant_name,
            model=self._config.assistant_model,
            file_search_vector_store_id=vector_store_id,
        )

        mcp_registry = GideonMcpRegistry(
            self._client.mcp
        )

        server = mcp_registry.ensure_server(
            name=self._config.playwright_mcp_name,
            url=self._config.playwright_mcp_url,
        )

        discovered = mcp_registry.discover(
            server
        )

        selected = select_playwright_preparation_tools(
            discovered
        )

        attached = mcp_registry.reconcile_assistant_tools(
            assistant_id=assistant.id,
            server=server,
            desired_tools=selected,
        )

        attached_playwright = [
            tool
            for tool in attached
            if _attachment_belongs_to_server(
                tool,
                server,
            )
        ]

        return ProjectDavidRuntimeBindings(
            assistant_name=self._config.assistant_name,
            assistant_id=assistant.id,
            mcp_server_name=self._config.playwright_mcp_name,
            mcp_server_id=server.id,
            meta_data={
                "ready": True,
                "file_search_vector_store_id": vector_store_id,
                "playwright_tool_names": selected.names(),
                "playwright_attached_count": len(
                    attached_playwright
                ),
            },
        )