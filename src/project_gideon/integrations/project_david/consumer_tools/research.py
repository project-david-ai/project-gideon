from __future__ import annotations

from collections.abc import Callable
from typing import Any

from project_gideon.models.delegation import (
    ResearchDelegationRequest,
)
from project_gideon.services.delegation import (
    ResearchDelegationService,
)


RESEARCH_DELEGATE_TOOL_NAME = "research_delegate"


def build_research_delegate_tool() -> dict[str, Any]:
    """
    Project David function-tool declaration derived directly from Gideon's
    Pydantic boundary contract.
    """

    return {
        "type": "function",
        "function": {
            "name": RESEARCH_DELEGATE_TOOL_NAME,
            "description": (
                "Delegate a bounded research objective to Gideon's dedicated "
                "research faction. Use this for evidence gathering, company "
                "research, market research, role research, or other tasks that "
                "require external research. The research faction returns "
                "knowledge and provenance; it does not mutate canonical "
                "Gideon domain state."
            ),
            "parameters": ResearchDelegationRequest.model_json_schema(),
        },
    }


def create_research_delegate_handler(
    service: ResearchDelegationService,
) -> Callable[[str, dict[str, Any]], str]:
    """
    Build the synchronous Project David consumer-tool handler.

    ToolCallRequestEvent.execute() supplies:
        handler(tool_name, arguments) -> str

    The returned string is the serialized typed result submitted back into
    the supervisor's Project David dialogue.
    """

    def handle(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        if tool_name != RESEARCH_DELEGATE_TOOL_NAME:
            raise ValueError(
                f"Research handler cannot execute tool={tool_name!r}."
            )

        request = ResearchDelegationRequest.model_validate(
            arguments
        )

        result = service.delegate(
            request
        )

        return result.model_dump_json(
            exclude_none=True
        )

    return handle