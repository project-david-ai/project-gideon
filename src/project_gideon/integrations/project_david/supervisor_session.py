from __future__ import annotations

from collections.abc import Callable
from typing import Any

from projectdavid import (
    ContentEvent,
    ToolCallRequestEvent,
)

from project_gideon.integrations.project_david.activity_projector import (
    ActivityProjector,
)
from project_gideon.integrations.project_david.consumer_tools.dispatcher import (
    ConsumerToolDispatcher,
)
from project_gideon.models.presentation import (
    GideonPresentationEvent,
)
from project_gideon.models.session import (
    SupervisorToolCallRecord,
    SupervisorTurnResult,
)


class SupervisorSessionError(RuntimeError):
    pass


class SupervisorSessionService:
    """
    Execute externally initiated turns for Gideon's career supervisor.

    This service owns the career faction's Project David inference lifecycle.

    It deliberately knows nothing about research_delegate, jobs_delegate,
    or any other specific faction. Consumer capabilities are supplied through
    the injected dispatcher.
    """

    def __init__(
        self,
        *,
        client,
        assistant_id: str,
        model: str,
        dispatcher: ConsumerToolDispatcher,
        provider_api_key: str | None = None,
        max_turns: int = 10,
        activity_projector: ActivityProjector | None = None,
        presentation_sink: Callable[
            [GideonPresentationEvent],
            None,
        ]
        | None = None,
    ) -> None:
        self._client = client
        self._assistant_id = assistant_id
        self._model = model
        self._dispatcher = dispatcher
        self._provider_api_key = provider_api_key
        self._max_turns = max_turns

        self._activity_projector = (
            activity_projector
            or ActivityProjector()
        )

        self._presentation_sink = presentation_sink

    def _present(
        self,
        event: GideonPresentationEvent,
    ) -> None:
        if self._presentation_sink is None:
            return

        if event.faction is None:
            event = event.model_copy(
                update={
                    "faction": "career",
                }
            )

        self._presentation_sink(
            event
        )

    @staticmethod
    def _career_meta_data(
        meta_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        result = dict(
            meta_data or {}
        )

        # The caller cannot impersonate another orchestration faction.
        result["gideon_faction"] = "career"

        return result

    def run(
        self,
        *,
        prompt: str,
        meta_data: dict[str, Any] | None = None,
    ) -> SupervisorTurnResult:
        if not prompt.strip():
            raise SupervisorSessionError(
                "Supervisor prompt must not be empty."
            )

        session_meta = self._career_meta_data(
            meta_data
        )

        thread = self._client.threads.create_thread(
            meta_data=session_meta
        )

        message = self._client.messages.create_message(
            thread_id=thread.id,
            role="user",
            content=prompt,
            assistant_id=self._assistant_id,
            meta_data=session_meta,
        )

        run = self._client.runs.create_run(
            assistant_id=self._assistant_id,
            thread_id=thread.id,
            meta_data=session_meta,
        )

        stream = self._client.synchronous_inference_stream

        stream.bind_clients(
            self._client.runs,
            self._client.actions,
            self._client.messages,
            self._client.assistants,
        )

        stream.setup(
            thread_id=thread.id,
            assistant_id=self._assistant_id,
            message_id=message.id,
            run_id=run.id,
            api_key=self._provider_api_key,
            meta_data=session_meta,
        )

        content_parts: list[str] = []
        tool_calls: list[SupervisorToolCallRecord] = []

        for event in stream.stream_events(
            model=self._model,
            max_turns=self._max_turns,
        ):
            for presentation_event in self._activity_projector.project(
                event
            ):
                self._present(
                    presentation_event
                )

            if isinstance(
                event,
                ToolCallRequestEvent,
            ):
                record = SupervisorToolCallRecord(
                    tool_name=event.tool_name,
                    arguments=dict(
                        event.args
                    ),
                    action_id=event.action_id,
                    tool_call_id=event.tool_call_id,
                    executed=False,
                )

                executed = self._dispatcher.execute_event(
                    event
                )

                tool_calls.append(
                    record.model_copy(
                        update={
                            "executed": bool(
                                executed
                            )
                        }
                    )
                )

                if not executed:
                    raise SupervisorSessionError(
                        "Project David did not complete consumer tool "
                        f"execution for tool={event.tool_name!r}."
                    )

                continue

            if isinstance(
                event,
                ContentEvent,
            ):
                try:
                    payload = event.to_dict()
                except Exception as exc:
                    raise SupervisorSessionError(
                        "Unable to serialize Project David content event."
                    ) from exc

                content = payload.get(
                    "content"
                )

                if isinstance(
                    content,
                    str,
                ):
                    content_parts.append(
                        content
                    )

        content = "".join(
            content_parts
        ).strip()

        if not content:
            raise SupervisorSessionError(
                "Supervisor completed without user-visible content."
            )

        self._present(
            self._activity_projector.final(
                run_id=run.id
            )
        )

        return SupervisorTurnResult(
            assistant_id=self._assistant_id,
            thread_id=thread.id,
            message_id=message.id,
            run_id=run.id,
            content=content,
            tool_calls=tool_calls,
            meta_data=session_meta,
        )
