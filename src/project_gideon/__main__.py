from __future__ import annotations

from project_gideon.integrations.project_david.bootstrap import (
    ProjectDavidBootstrap,
)
from project_gideon.integrations.project_david.client import (
    ProjectDavidClientFactory,
)
from project_gideon.integrations.project_david.config import (
    load_project_david_config,
)


def main() -> None:
    """
    Start Gideon only after its Project David runtime composition is ready.

    Startup readiness requires successful reconciliation of:
    - the Gideon supervisor assistant;
    - the configured Playwright MCP registration;
    - the governed Playwright capability set;
    - durable assistant MCP attachments.

    Any reconciliation failure aborts process startup.
    """

    config = load_project_david_config()

    client = ProjectDavidClientFactory(
        config
    ).create()

    bindings = ProjectDavidBootstrap(
        client=client,
        config=config,
    ).reconcile()

    if not bindings.meta_data.get(
        "ready",
        False,
    ):
        raise RuntimeError(
            "Project David bootstrap completed without ready state."
        )

    print(
        "PROJECT_GIDEON_RUNTIME_READY "
        f"assistant_id={bindings.assistant_id} "
        f"mcp_server_id={bindings.mcp_server_id} "
        f"playwright_tools="
        f"{bindings.meta_data['playwright_attached_count']}"
    )


if __name__ == "__main__":
    main()