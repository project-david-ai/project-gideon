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


def test_supervisor_advertises_both_cross_faction_tools():
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
    ]

    assert (
        "jobs_delegate"
        in assistant.instructions
    )

    assert (
        "canonical job"
        in assistant.instructions.lower()
    )
