from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from project_gideon.models.application_campaign import (
    ApplicationCampaignAction,
    ApplicationCampaignRequest,
    ApplicationCampaignResult,
)
from project_gideon.services.application_campaign import (
    ApplicationCampaignService,
)


APPLICATION_CAMPAIGN_TOOL_NAME = "application_campaign"


def build_application_campaign_tool() -> dict[str, Any]:
    """
    Project David function-tool declaration for durable campaign operations.

    The schema is derived from Gideon's typed domain boundary.
    """

    return {
        "type": "function",
        "function": {
            "name": APPLICATION_CAMPAIGN_TOOL_NAME,
            "description": (
                "Mutate Gideon's authoritative application-campaign state. "
                "Use shortlist to create or reuse the durable application "
                "campaign for a canonical job and candidate. Use "
                "start_preparation to move an existing shortlisted "
                "application into preparation. Do not invent canonical IDs "
                "or bypass Gideon's lifecycle service."
            ),
            "parameters": (
                ApplicationCampaignRequest.model_json_schema()
            ),
        },
    }


def _run_campaign_operation(
    operation,
):
    """
    Bridge Gideon's async repository-backed domain service into Project
    David's synchronous consumer-tool callback contract.

    SupervisorSessionService currently executes Project David's synchronous
    ToolCallRequestEvent.execute(handler) surface, so a running event loop is
    treated as a composition error rather than silently nesting one.
    """

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            operation()
        )

    raise RuntimeError(
        "Application campaign consumer tool requires Project David's "
        "synchronous consumer-tool execution context."
    )


def create_application_campaign_handler(
    service: ApplicationCampaignService,
) -> Callable[
    [str, dict[str, Any]],
    str,
]:
    """
    Build the synchronous Project David consumer-tool handler.

    ToolCallRequestEvent.execute() remains responsible for action lifecycle,
    tool-output submission, and Turn N continuation.
    """

    def handle(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        if tool_name != APPLICATION_CAMPAIGN_TOOL_NAME:
            raise ValueError(
                "Application campaign handler cannot execute "
                f"tool={tool_name!r}."
            )

        request = ApplicationCampaignRequest.model_validate(
            arguments
        )

        if (
            request.action
            is ApplicationCampaignAction.SHORTLIST
        ):
            application = _run_campaign_operation(
                lambda: service.shortlist(
                    tenant_id=request.tenant_id,
                    job_id=request.job_id,
                    candidate_id=request.candidate_id,
                )
            )

        elif (
            request.action
            is ApplicationCampaignAction.START_PREPARATION
        ):
            application = _run_campaign_operation(
                lambda: service.start_preparation(
                    application_id=request.application_id,
                    tenant_id=request.tenant_id,
                )
            )

        else:
            raise ValueError(
                f"Unsupported application campaign action: "
                f"{request.action!r}."
            )

        result = ApplicationCampaignResult(
            action=request.action,
            application=application,
        )

        return result.model_dump_json(
            exclude_none=True
        )

    return handle
