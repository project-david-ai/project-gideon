import json

import pytest
from pydantic import ValidationError

from project_gideon.integrations.project_david.consumer_tools.application_campaign import (
    APPLICATION_CAMPAIGN_TOOL_NAME,
    build_application_campaign_tool,
    create_application_campaign_handler,
)
from project_gideon.models import (
    ApplicationCampaignAction,
    ApplicationState,
    JobApplication,
)


class FakeCampaignService:
    def __init__(self):
        self.calls = []

    async def shortlist(
        self,
        *,
        tenant_id,
        job_id,
        candidate_id,
    ):
        self.calls.append(
            (
                "shortlist",
                tenant_id,
                job_id,
                candidate_id,
            )
        )

        return JobApplication(
            id="application_1",
            tenant_id=tenant_id,
            job_id=job_id,
            candidate_id=candidate_id,
            state=ApplicationState.SHORTLISTED,
        )

    async def start_preparation(
        self,
        *,
        application_id,
        tenant_id,
    ):
        self.calls.append(
            (
                "start_preparation",
                tenant_id,
                application_id,
            )
        )

        return JobApplication(
            id=application_id,
            tenant_id=tenant_id,
            job_id="job_1",
            candidate_id="candidate_1",
            state=ApplicationState.PREPARING,
        )


def test_campaign_tool_schema_is_function_tool():
    tool = build_application_campaign_tool()

    assert tool["type"] == "function"

    function = tool["function"]

    assert (
        function["name"]
        == APPLICATION_CAMPAIGN_TOOL_NAME
    )

    required = set(
        function["parameters"]["required"]
    )

    assert "tenant_id" in required
    assert "action" in required


def test_campaign_tool_exposes_explicit_action_enum():
    tool = build_application_campaign_tool()

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
        "ApplicationCampaignAction"
    ]

    assert set(
        action_schema["enum"]
    ) == {
        "shortlist",
        "start_preparation",
    }


def test_campaign_handler_shortlists_through_typed_service():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    payload = handler(
        APPLICATION_CAMPAIGN_TOOL_NAME,
        {
            "tenant_id": "tenant_1",
            "action": "shortlist",
            "job_id": "job_1",
            "candidate_id": "candidate_1",
        },
    )

    decoded = json.loads(
        payload
    )

    assert service.calls == [
        (
            "shortlist",
            "tenant_1",
            "job_1",
            "candidate_1",
        )
    ]

    assert decoded["action"] == "shortlist"

    assert (
        decoded["application"]["state"]
        == "shortlisted"
    )

    assert (
        decoded["application"]["id"]
        == "application_1"
    )


def test_campaign_handler_starts_preparation():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    payload = handler(
        APPLICATION_CAMPAIGN_TOOL_NAME,
        {
            "tenant_id": "tenant_1",
            "action": "start_preparation",
            "application_id": "application_1",
        },
    )

    decoded = json.loads(
        payload
    )

    assert service.calls == [
        (
            "start_preparation",
            "tenant_1",
            "application_1",
        )
    ]

    assert (
        decoded["application"]["state"]
        == "preparing"
    )


def test_campaign_handler_rejects_missing_shortlist_identity():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    with pytest.raises(
        ValidationError,
        match="candidate_id",
    ):
        handler(
            APPLICATION_CAMPAIGN_TOOL_NAME,
            {
                "tenant_id": "tenant_1",
                "action": "shortlist",
                "job_id": "job_1",
            },
        )

    assert service.calls == []


def test_campaign_handler_rejects_missing_application_id():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    with pytest.raises(
        ValidationError,
        match="application_id",
    ):
        handler(
            APPLICATION_CAMPAIGN_TOOL_NAME,
            {
                "tenant_id": "tenant_1",
                "action": "start_preparation",
            },
        )

    assert service.calls == []


def test_campaign_handler_rejects_wrong_tool_name():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    with pytest.raises(
        ValueError,
        match="Application campaign handler",
    ):
        handler(
            "jobs_delegate",
            {
                "tenant_id": "tenant_1",
                "action": "shortlist",
                "job_id": "job_1",
                "candidate_id": "candidate_1",
            },
        )

    assert service.calls == []


@pytest.mark.asyncio
async def test_campaign_handler_rejects_nested_event_loop():
    service = FakeCampaignService()

    handler = create_application_campaign_handler(
        service
    )

    with pytest.raises(
        RuntimeError,
        match="synchronous consumer-tool execution context",
    ):
        handler(
            APPLICATION_CAMPAIGN_TOOL_NAME,
            {
                "tenant_id": "tenant_1",
                "action": "shortlist",
                "job_id": "job_1",
                "candidate_id": "candidate_1",
            },
        )

    assert service.calls == []


def test_campaign_models_are_exported():
    assert (
        ApplicationCampaignAction.SHORTLIST.value
        == "shortlist"
    )
