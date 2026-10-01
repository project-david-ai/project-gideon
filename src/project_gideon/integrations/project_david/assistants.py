from __future__ import annotations

from typing import Any, Protocol, Sequence


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
""".strip()


class AssistantsClientProtocol(Protocol):
    def list_assistants(self) -> Sequence[Any]:
        ...

    def create_assistant(self, **kwargs: Any) -> Any:
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

    The assistant ID is discovered from Project David and must not be
    hard-coded into Gideon configuration.
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
    ) -> Any:
        matches = [
            assistant
            for assistant in self._assistants.list_assistants()
            if getattr(assistant, "name", None) == name
        ]

        if len(matches) > 1:
            raise AssistantReconciliationError(
                f"Multiple Project David assistants exist with "
                f"logical name={name!r}."
            )

        if matches:
            assistant = matches[0]

            return self._assistants.update_assistant(
                assistant_id=assistant.id,
                name=name,
                model=model,
                instructions=GIDEON_SUPERVISOR_INSTRUCTIONS,
            )

        return self._assistants.create_assistant(
            name=name,
            model=model,
            instructions=GIDEON_SUPERVISOR_INSTRUCTIONS,
            tools=[],
        )