from __future__ import annotations

from typing import Any, Protocol, Sequence

from project_gideon.integrations.project_david.consumer_tools.application_campaign import (
    build_application_campaign_tool,
)
from project_gideon.integrations.project_david.consumer_tools.jobs import (
    build_jobs_delegate_tool,
)
from project_gideon.integrations.project_david.consumer_tools.research import (
    build_research_delegate_tool,
)


GIDEON_SUPERVISOR_INSTRUCTIONS = """
You are Gideon, a career-search supervisor.

You coordinate job discovery, company research, fit analysis,
application preparation, and interview preparation.

Durable application state is owned by Gideon's application services.
Do not invent candidate facts.

Unknown or ambiguous application questions must be surfaced rather than
guessed.

You may prepare an application, but external submission requires explicit
user approval enforced by Gideon's application services.

When external evidence gathering or substantial research is required, use
research_delegate. The research faction owns its own research orchestration;
you remain the career supervisor.

When job discovery, ingestion, or refresh of canonical job-domain state is
required, use jobs_delegate. The jobs faction owns job acquisition and
canonical job reconciliation; you remain the career supervisor.

When the user wants to shortlist a canonical job or begin preparing an
existing shortlisted application, use application_campaign. Gideon's
application services own durable campaign state and lifecycle rules; never
invent canonical job, candidate, or application identifiers.
""".strip()


class AssistantsClientProtocol(Protocol):
    def list_assistants(self) -> Sequence[Any]:
        ...

    def create_assistant(
        self,
        **kwargs: Any,
    ) -> Any:
        ...

    def update_assistant(
        self,
        assistant_id: str,
        **updates: Any,
    ) -> Any:
        ...


class AssistantReconciliationError(RuntimeError):
    pass


class GideonAssistantRegistry:
    """
    Reconcile Gideon's logical supervisor identity with Project David.

    Runtime IDs are Project David resources and are never configuration.
    """

    def __init__(
        self,
        assistants: AssistantsClientProtocol,
    ) -> None:
        self._assistants = assistants

    def ensure_supervisor(
        self,
        *,
        name: str,
        model: str,
        file_search_vector_store_id: str | None = None,
    ) -> Any:
        matches = [
            assistant
            for assistant in self._assistants.list_assistants()
            if getattr(
                assistant,
                "name",
                None,
            ) == name
        ]

        if len(matches) > 1:
            raise AssistantReconciliationError(
                f"Multiple Project David assistants exist with "
                f"logical name={name!r}."
            )

        tools = [
            build_research_delegate_tool(),
            build_jobs_delegate_tool(),
            build_application_campaign_tool(),
        ]

        updates = {
            "name": name,
            "model": model,
            "instructions": GIDEON_SUPERVISOR_INSTRUCTIONS,
            "tools": tools,
        }

        if file_search_vector_store_id:
            updates["tool_resources"] = {
                "file_search": {
                    "vector_store_ids": [
                        file_search_vector_store_id,
                    ],
                },
            }

        if matches:
            assistant = matches[0]

            return self._assistants.update_assistant(
                assistant_id=assistant.id,
                **updates,
            )

        return self._assistants.create_assistant(
            **updates,
        )