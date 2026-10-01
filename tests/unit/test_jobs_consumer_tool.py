import json

from project_gideon.integrations.project_david.consumer_tools.jobs import (
    JOBS_DELEGATE_TOOL_NAME,
    build_jobs_delegate_tool,
    create_jobs_delegate_handler,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationResult,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
)


def test_jobs_tool_schema_is_function_tool():
    tool = build_jobs_delegate_tool()

    assert tool["type"] == "function"

    function = tool["function"]

    assert (
        function["name"]
        == JOBS_DELEGATE_TOOL_NAME
    )

    required = set(
        function["parameters"]["required"]
    )

    assert "tenant_id" in required
    assert "action" in required


def test_jobs_tool_exposes_explicit_action_enum():
    tool = build_jobs_delegate_tool()

    schema = tool[
        "function"
    ][
        "parameters"
    ]

    definitions = schema.get(
        "$defs",
        {}
    )

    action_schema = definitions[
        "JobsDelegationAction"
    ]

    assert set(
        action_schema["enum"]
    ) == {
        "discover",
        "ingest",
        "refresh",
    }


def test_jobs_handler_validates_and_serializes_typed_result():
    observed = []

    class FakeJobsPort:
        def delegate_jobs(
            self,
            request,
        ):
            observed.append(
                request
            )

            return JobsDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                job_ids=[
                    "job-1",
                    "job-2",
                ],
                discovered_count=3,
                ingested_count=2,
                duplicate_count=1,
            )

    handler = create_jobs_delegate_handler(
        JobsDelegationService(
            FakeJobsPort()
        )
    )

    payload = handler(
        "jobs_delegate",
        {
            "tenant_id": "tenant-1",
            "action": "discover",
            "query": "senior network engineer",
            "parameters": {
                "location": "Germany",
            },
        },
    )

    decoded = json.loads(
        payload
    )

    assert len(observed) == 1

    request = observed[0]

    assert request.tenant_id == "tenant-1"

    assert (
        request.action
        is JobsDelegationAction.DISCOVER
    )

    assert (
        request.query
        == "senior network engineer"
    )

    assert decoded["status"] == "succeeded"

    assert decoded["job_ids"] == [
        "job-1",
        "job-2",
    ]

    assert decoded["discovered_count"] == 3
    assert decoded["ingested_count"] == 2
    assert decoded["duplicate_count"] == 1


def test_jobs_handler_rejects_wrong_tool_name():
    class FakeJobsPort:
        def delegate_jobs(
            self,
            request,
        ):
            raise AssertionError(
                "Port must not be invoked."
            )

    handler = create_jobs_delegate_handler(
        JobsDelegationService(
            FakeJobsPort()
        )
    )

    try:
        handler(
            "research_delegate",
            {
                "tenant_id": "tenant-1",
                "action": "discover",
            },
        )
    except ValueError as exc:
        assert "Jobs handler" in str(
            exc
        )
    else:
        raise AssertionError(
            "Expected wrong tool name to be rejected."
        )
