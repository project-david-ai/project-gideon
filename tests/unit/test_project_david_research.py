from types import SimpleNamespace

from project_gideon.integrations.project_david.research import (
    ProjectDavidResearchDelegationPort,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    ResearchDelegationRequest,
)


class FakeContentEvent:
    def __init__(
        self,
        content,
    ):
        self._content = content

    def to_dict(
        self,
    ):
        return {
            "content": self._content,
        }


def test_research_adapter_reconciles_dedicated_assistant():
    created = []

    class FakeAssistants:
        def list_assistants(
            self,
        ):
            return []

        def create_assistant(
            self,
            **kwargs,
        ):
            created.append(
                kwargs
            )

            return SimpleNamespace(
                id="research-assistant-1",
                name=kwargs["name"],
            )

    client = SimpleNamespace(
        assistants=FakeAssistants(),
    )

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: client,
        model="test-model",
    )

    assistant = port._ensure_research_assistant()

    assert assistant.id == "research-assistant-1"

    assert created[0]["deep_research"] is True
    assert created[0]["web_access"] is True
    assert created[0]["agent_mode"] is True
    assert created[0]["tools"] == [
        {
            "type": "web_search",
        }
    ]


def test_research_adapter_updates_existing_assistant():
    updates = []

    existing = SimpleNamespace(
        id="research-assistant-1",
        name="gideon-research-supervisor",
    )

    class FakeAssistants:
        def list_assistants(
            self,
        ):
            return [
                existing
            ]

        def update_assistant(
            self,
            assistant_id,
            **kwargs,
        ):
            updates.append(
                (
                    assistant_id,
                    kwargs,
                )
            )

            return existing

    client = SimpleNamespace(
        assistants=FakeAssistants(),
    )

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: client,
        model="test-model",
    )

    result = port._ensure_research_assistant()

    assert result is existing
    assert updates[0][0] == "research-assistant-1"
    assert updates[0][1]["deep_research"] is True
    assert updates[0][1]["tools"] == [
        {
            "type": "web_search",
        }
    ]


def test_research_prompt_contains_only_bounded_request():
    request = ResearchDelegationRequest(
        tenant_id="tenant-1",
        objective="Research Acme.",
        context={
            "job_id": "job-1",
        },
        max_depth=3,
    )

    prompt = ProjectDavidResearchDelegationPort._build_prompt(
        request
    )

    assert "Research Acme." in prompt
    assert '"job_id": "job-1"' in prompt
    assert '"max_depth": 3' in prompt

def test_research_adapter_lazily_owns_isolated_client():
    created_clients = []

    research_client = SimpleNamespace()

    def factory():
        created_clients.append(
            research_client
        )

        return research_client

    port = ProjectDavidResearchDelegationPort(
        client_factory=factory,
        model="test-model",
    )

    assert port._client is None

    first = port._get_client()
    second = port._get_client()

    assert first is research_client
    assert second is research_client

    assert created_clients == [
        research_client,
    ]


def test_research_assistant_requires_web_search_and_deep_research():
    created = []

    class FakeAssistants:
        def list_assistants(
            self,
        ):
            return []

        def create_assistant(
            self,
            **kwargs,
        ):
            created.append(
                kwargs
            )

            return SimpleNamespace(
                id="research-assistant-1",
                name=kwargs["name"],
            )

    research_client = SimpleNamespace(
        assistants=FakeAssistants(),
    )

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: research_client,
        model="test-model",
    )

    port._ensure_research_assistant()

    assert created[0]["deep_research"] is True

    assert created[0]["tools"] == [
        {
            "type": "web_search",
        }
    ]
