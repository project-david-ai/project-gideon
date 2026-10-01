from project_gideon.integrations.project_david.client import (
    ProjectDavidClientFactory,
)
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)


def test_research_client_is_distinct_entity_instance():
    config = ProjectDavidConfig(
        base_url="http://project-david.example",
        api_key="test-key",
        assistant_name="gideon",
        assistant_model="test-model",
        playwright_mcp_name="playwright-primary",
        playwright_mcp_url="http://playwright.example/mcp",
    )

    factory = ProjectDavidClientFactory(
        config
    )

    supervisor_client = factory.create()
    research_client = factory.create_research_client()

    assert supervisor_client is not research_client

    assert supervisor_client.base_url == research_client.base_url
    assert supervisor_client.api_key == research_client.api_key