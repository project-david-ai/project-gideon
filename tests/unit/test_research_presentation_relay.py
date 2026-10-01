from types import SimpleNamespace

from project_gideon.integrations.project_david.research import (
    ProjectDavidResearchDelegationPort,
)
from project_gideon.models.presentation import (
    PresentationEventType,
    PresentationState,
)


def test_research_port_relays_projected_activity_with_faction_identity():
    observed = []

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: SimpleNamespace(),
        model="test-model",
        provider_api_key="test-provider-key",
    )

    port.bind_presentation(
        presentation_sink=observed.append,
    )

    port._relay_presentation_event(
        {
            "type": "web_status",
            "run_id": "research-run-1",
            "status": "running",
            "tool": "read_web_page",
            "message": "Reading: https://www.python.org/downloads/",
        }
    )

    assert len(observed) == 1

    event = observed[0]

    assert event.type is PresentationEventType.SOURCE
    assert event.state is PresentationState.IN_PROGRESS
    assert event.faction == "research"

    assert (
        event.source_url
        == "https://www.python.org/downloads/"
    )


def test_research_port_does_not_relay_reasoning():
    observed = []

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: SimpleNamespace(),
        model="test-model",
        provider_api_key="test-provider-key",
    )

    port.bind_presentation(
        presentation_sink=observed.append,
    )

    port._relay_presentation_event(
        {
            "type": "reasoning",
            "run_id": "research-run-1",
            "content": "private internal reasoning",
        }
    )

    assert observed == []


def test_research_port_does_not_expose_raw_scratchpad_entry():
    observed = []

    port = ProjectDavidResearchDelegationPort(
        client_factory=lambda: SimpleNamespace(),
        model="test-model",
        provider_api_key="test-provider-key",
    )

    port.bind_presentation(
        presentation_sink=observed.append,
    )

    port._relay_presentation_event(
        {
            "type": "scratchpad_status",
            "run_id": "research-run-1",
            "operation": "append",
            "state": "success",
            "tool": "append_scratchpad",
            "activity": "Appending research notes",
            "entry": "✅ PRIVATE WORKING MATERIAL",
            "assistant_id": "worker-1",
        }
    )

    assert len(observed) == 1

    event = observed[0]

    assert event.faction == "research"
    assert event.title == "Completed a research step"

    assert (
        "PRIVATE WORKING MATERIAL"
        not in event.model_dump_json()
    )
