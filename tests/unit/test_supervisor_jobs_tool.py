from types import SimpleNamespace

from project_gideon.integrations.project_david.assistants import (
    GideonAssistantRegistry,
)


class FakeAssistants:
    def __init__(
        self,
    ):
        self.created = []

    def list_assistants(
        self,
    ):
        return []

    def create_assistant(
        self,
        **kwargs,
    ):
        self.created.append(
            kwargs
        )

        return SimpleNamespace(
            id="assistant-1",
            **kwargs,
        )

    def update_assistant(
        self,
        assistant_id,
        **kwargs,
    ):
        raise AssertionError(
            "Update should not be used."
        )


def test_supervisor_advertises_domain_and_cross_faction_tools():
    client = FakeAssistants()

    registry = GideonAssistantRegistry(
        client
    )

    assistant = registry.ensure_supervisor(
        name="gideon-supervisor",
        model="test-model",
    )

    names = [
        tool["function"]["name"]
        for tool in assistant.tools
        if tool.get("type") == "function"
    ]

    assert names == [
        "research_delegate",
        "jobs_delegate",
        "job_lookup",
        "application_campaign",
    ]

    assert (
        "jobs_delegate"
        in assistant.instructions
    )

    assert (
        "canonical job"
        in assistant.instructions.lower()
    )

    assert (
        "application_campaign"
        in assistant.instructions
    )

    assert (
        "durable campaign state"
        in assistant.instructions.lower()
    )


def test_supervisor_reconciles_native_file_search_tool_resources() -> None:
    from types import SimpleNamespace

    from project_gideon.integrations.project_david.assistants import (
        GideonAssistantRegistry,
    )

    class FakeAssistants:
        def __init__(self) -> None:
            self.updates = []

        def list_assistants(self):
            return [
                SimpleNamespace(
                    id="asst-existing",
                    name="gideon-supervisor",
                )
            ]

        def update_assistant(self, assistant_id, **updates):
            self.updates.append((assistant_id, updates))
            return SimpleNamespace(
                id=assistant_id,
                name=updates["name"],
            )

        def create_assistant(self, **kwargs):
            raise AssertionError(
                "Existing supervisor must be reconciled, not recreated."
            )

    client = FakeAssistants()

    GideonAssistantRegistry(
        client
    ).ensure_supervisor(
        name="gideon-supervisor",
        model="test-model",
        file_search_vector_store_id="vect-candidate",
    )

    assert len(client.updates) == 1

    _, updates = client.updates[0]

    assert {
        "type": "file_search",
    } in updates["tools"]

    assert updates["tool_resources"] == {
        "file_search": {
            "vector_store_ids": [
                "vect-candidate",
            ],
        },
    }


def test_supervisor_without_vector_store_does_not_invent_tool_resources() -> None:
    from types import SimpleNamespace

    from project_gideon.integrations.project_david.assistants import (
        GideonAssistantRegistry,
    )

    class FakeAssistants:
        def __init__(self) -> None:
            self.created = None

        def list_assistants(self):
            return []

        def create_assistant(self, **kwargs):
            self.created = kwargs
            return SimpleNamespace(
                id="asst-created",
                name=kwargs["name"],
            )

        def update_assistant(self, assistant_id, **updates):
            raise AssertionError(
                "Missing supervisor should be created."
            )

    client = FakeAssistants()

    GideonAssistantRegistry(
        client
    ).ensure_supervisor(
        name="gideon-supervisor",
        model="test-model",
    )

    assert client.created is not None
    assert "tool_resources" not in client.created
    assert not any(
        tool.get("type") == "file_search"
        for tool in client.created["tools"]
    )
