from __future__ import annotations

from collections.abc import Callable
from typing import Any

from project_gideon.models.delegation import (
    JobsDelegationRequest,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
)


JOBS_DELEGATE_TOOL_NAME = "jobs_delegate"


def build_jobs_delegate_tool() -> dict[str, Any]:
    """
    Project David function-tool declaration for Gideon's jobs faction.

    The schema is derived directly from the typed cross-faction request.
    """

    return {
        "type": "function",
        "function": {
            "name": JOBS_DELEGATE_TOOL_NAME,
            "description": (
                "Delegate job-domain work to Gideon's dedicated jobs faction. "
                "Use this for job discovery, ingestion, or refresh operations. "
                "For employer-specific discovery, supply typed employer targets "
                "through employers; ATS provider and board identifiers are "
                "resolved by the jobs faction and should not be guessed. "
                "The jobs faction may create or reconcile authoritative "
                "canonical Job records and returns canonical job identifiers."
            ),
            "parameters": JobsDelegationRequest.model_json_schema(),
        },
    }


def create_jobs_delegate_handler(
    service: JobsDelegationService,
) -> Callable[
    [str, dict[str, Any]],
    str,
]:
    """
    Build the synchronous Project David consumer-tool handler.

    ToolCallRequestEvent.execute() owns the Project David action lifecycle.
    The handler validates the typed request and returns the serialized typed
    JobsDelegationResult.
    """

    def handle(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        if tool_name != JOBS_DELEGATE_TOOL_NAME:
            raise ValueError(
                f"Jobs handler cannot execute tool={tool_name!r}."
            )

        request = JobsDelegationRequest.model_validate(
            arguments
        )

        result = service.delegate(
            request
        )

        return result.model_dump_json(
            exclude_none=True
        )

    return handle
