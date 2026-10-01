from __future__ import annotations

import os
from typing import Iterable, Optional

from pydantic import BaseModel


class ProjectDavidConfig(BaseModel):
    base_url: str
    api_key: str

    assistant_name: str = "gideon-supervisor"
    assistant_model: str

    playwright_mcp_name: str = "playwright-primary"
    playwright_mcp_url: str


def _first_env(
    names: Iterable[str],
) -> Optional[str]:
    for name in names:
        value = os.getenv(name)

        if value:
            return value

    return None


def load_project_david_config() -> ProjectDavidConfig:
    """
    Resolve Gideon's canonical runtime settings.

    Verified development compatibility:
      PROJECTDAVID_BASE_URL
        -> BASE_URL

      PROJECTDAVID_API_KEY
        -> DEV_PROJECT_DAVID_CORE_TEST_USER_KEY

      GIDEON_ASSISTANT_MODEL
        -> MCP_TEST_MODEL_ID

    Canonical Gideon names always take precedence.
    """

    base_url = _first_env(
        (
            "PROJECTDAVID_BASE_URL",
            "BASE_URL",
            "PROJECT_DAVID_PLATFORM_BASE_URL",
            "ENTITIES_BASE_URL",
        )
    )

    api_key = _first_env(
        (
            "PROJECTDAVID_API_KEY",
            "DEV_PROJECT_DAVID_CORE_TEST_USER_KEY",
        )
    )

    assistant_model = _first_env(
        (
            "GIDEON_ASSISTANT_MODEL",
            "MCP_TEST_MODEL_ID",
        )
    )

    playwright_mcp_url = _first_env(
        (
            "PLAYWRIGHT_MCP_URL",
        )
    )

    missing = []

    if not base_url:
        missing.append("PROJECTDAVID_BASE_URL")

    if not api_key:
        missing.append("PROJECTDAVID_API_KEY")

    if not assistant_model:
        missing.append("GIDEON_ASSISTANT_MODEL")

    if not playwright_mcp_url:
        missing.append("PLAYWRIGHT_MCP_URL")

    if missing:
        raise RuntimeError(
            "Missing required Project David configuration: "
            + ", ".join(missing)
        )

    return ProjectDavidConfig(
        base_url=base_url,
        api_key=api_key,
        assistant_name=os.getenv(
            "GIDEON_ASSISTANT_NAME",
            "gideon-supervisor",
        ),
        assistant_model=assistant_model,
        playwright_mcp_name=os.getenv(
            "PLAYWRIGHT_MCP_NAME",
            "playwright-primary",
        ),
        playwright_mcp_url=playwright_mcp_url,
    )