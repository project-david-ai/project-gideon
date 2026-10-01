import json

from project_gideon.integrations.project_david.consumer_tools.research import (
    RESEARCH_DELEGATE_TOOL_NAME,
    build_research_delegate_tool,
    create_research_delegate_handler,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    ResearchDelegationResult,
)
from project_gideon.services.delegation import (
    ResearchDelegationService,
)


def test_research_tool_schema_is_function_tool():
    tool = build_research_delegate_tool()

    assert tool["type"] == "function"

    function = tool["function"]

    assert (
        function["name"]
        == RESEARCH_DELEGATE_TOOL_NAME
    )

    required = set(
        function["parameters"]["required"]
    )

    assert "tenant_id" in required
    assert "objective" in required


def test_research_handler_validates_and_serializes_typed_result():
    observed = []

    class FakePort:
        def delegate_research(
            self,
            request,
        ):
            observed.append(
                request
            )

            return ResearchDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                report="Acme report.",
                research_run_id="run-research-1",
                thread_id="thread-research-1",
            )

    handler = create_research_delegate_handler(
        ResearchDelegationService(
            FakePort()
        )
    )

    payload = handler(
        "research_delegate",
        {
            "tenant_id": "tenant-1",
            "objective": "Research Acme.",
            "context": {
                "job_id": "job-1",
            },
        },
    )

    decoded = json.loads(
        payload
    )

    assert len(observed) == 1
    assert observed[0].tenant_id == "tenant-1"
    assert observed[0].objective == "Research Acme."

    assert decoded["status"] == "succeeded"
    assert decoded["report"] == "Acme report."
    assert decoded["research_run_id"] == "run-research-1"