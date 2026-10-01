from __future__ import annotations

from project_gideon.integrations.project_david.assistants import (
    GideonAssistantRegistry,
)
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.mcp_registry import (
    GideonMcpRegistry,
)
from project_gideon.models import (
    ProjectDavidRuntimeBindings,
)


class ProjectDavidBootstrap:
    """
    Idempotently resolve Gideon's Project David resources.

    Tool attachment is deliberately not performed until Gideon has
    reconciled the actual discovered Playwright tool names against its
    semantic capability policy.
    """

    def __init__(
        self,
        *,
        client,
        config: ProjectDavidConfig,
    ) -> None:
        self._client = client
        self._config = config

    def reconcile(self) -> ProjectDavidRuntimeBindings:
        assistant_registry = GideonAssistantRegistry(
            self._client.assistants
        )

        assistant = assistant_registry.ensure_supervisor(
            name=self._config.assistant_name,
            model=self._config.assistant_model,
        )

        mcp_registry = GideonMcpRegistry(
            self._client.mcp
        )

        server = mcp_registry.ensure_server(
            name=self._config.playwright_mcp_name,
            url=self._config.playwright_mcp_url,
        )

        # Deliberate discovery only.
        #
        # We do NOT attach all tools here. The discovered collection must
        # first be reconciled with Gideon's explicit capability policy.
        mcp_registry.discover(server)

        return ProjectDavidRuntimeBindings(
            assistant_name=self._config.assistant_name,
            assistant_id=assistant.id,
            mcp_server_name=self._config.playwright_mcp_name,
            mcp_server_id=server.id,
        )