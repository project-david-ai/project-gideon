from __future__ import annotations

from projectdavid import Entity

from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)


class ProjectDavidClientFactory:
    """
    The only place Gideon constructs the Project David SDK Entity client.
    """

    def __init__(
        self,
        config: ProjectDavidConfig,
    ) -> None:
        self._config = config

    def create(self) -> Entity:
        return Entity(
            base_url=self._config.base_url,
            api_key=self._config.api_key,
        )