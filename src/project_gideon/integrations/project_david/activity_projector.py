from __future__ import annotations

from typing import Any

from project_gideon.models.presentation import (
    GideonPresentationEvent,
    PresentationEventType,
    PresentationState,
)


STATUS_MAP = {
    "started": PresentationState.IN_PROGRESS,
    "running": PresentationState.IN_PROGRESS,
    "in_progress": PresentationState.IN_PROGRESS,
    "complete": PresentationState.SUCCESS,
    "completed": PresentationState.SUCCESS,
    "done": PresentationState.SUCCESS,
    "success": PresentationState.SUCCESS,
    "inference_complete": PresentationState.SUCCESS,
    "warning": PresentationState.WARNING,
    "failed": PresentationState.ERROR,
    "error": PresentationState.ERROR,
}


WEB_TITLES = {
    "perform_web_search": "Searching the web",
    "read_web_page": "Reading a source",
    "search_web_page": "Searching within a source",
    "scroll_web_page": "Inspecting more of a source",
}


SCRATCHPAD_TITLES = {
    "📌": "Recorded a research strategy",
    "✅": "Completed a research step",
    "🔄": "Revised the research approach",
    "❓": "Identified an open question",
    "⚠️": "Encountered a research issue",
    "☠️": "Abandoned an unproductive path",
}


def _normalise_state(
    value: Any,
) -> PresentationState:
    if not isinstance(
        value,
        str,
    ):
        return PresentationState.INFO

    return STATUS_MAP.get(
        value.lower(),
        PresentationState.INFO,
    )


def _payload_from_event(
    event: Any,
) -> dict[str, Any]:
    if isinstance(
        event,
        dict,
    ):
        return dict(
            event
        )

    try:
        payload = event.to_dict()
    except Exception:
        return {}

    if isinstance(
        payload,
        dict,
    ):
        return payload

    return {}


class ActivityProjector:
    """
    Translate Project David stream events into Gideon's stable presentation
    contract.

    Raw model reasoning and raw scratchpad contents are intentionally not
    surfaced. The user sees meaningful lifecycle activity rather than internal
    token streams or working-memory dumps.
    """

    def project(
        self,
        event: Any,
    ) -> list[GideonPresentationEvent]:
        payload = _payload_from_event(
            event
        )

        event_type = payload.get(
            "type"
        )

        if not isinstance(
            event_type,
            str,
        ):
            return []

        run_id = payload.get(
            "run_id"
        )

        # ----------------------------------------------------------
        # Raw reasoning is not a user-facing presentation primitive.
        # ----------------------------------------------------------

        if event_type == "reasoning":
            return []

        # ----------------------------------------------------------
        # Ordinary assistant content remains owned by the chat
        # response accumulator, not the progress/activity surface.
        # ----------------------------------------------------------

        if event_type == "content":
            return []

        # ----------------------------------------------------------
        # Deep-research / delegation lifecycle
        # ----------------------------------------------------------

        if event_type in {
            "research_status",
            "activity",
        }:
            state = _normalise_state(
                payload.get(
                    "state",
                    payload.get(
                        "status"
                    ),
                )
            )

            activity = (
                payload.get("activity")
                or payload.get("message")
                or "Research activity"
            )

            tool = payload.get(
                "tool"
            )

            return [
                GideonPresentationEvent(
                    type=PresentationEventType.PHASE,
                    state=state,
                    phase="research",
                    title=str(
                        activity
                    ),
                    run_id=run_id,
                    tool=tool,
                )
            ]

        # ----------------------------------------------------------
        # Web lifecycle
        # ----------------------------------------------------------

        if event_type == "web_status":
            tool = payload.get(
                "tool"
            )

            state = _normalise_state(
                payload.get(
                    "status"
                )
            )

            message = payload.get(
                "message"
            )

            title = WEB_TITLES.get(
                str(
                    tool
                ),
                "Researching a source",
            )

            source_url = None

            if isinstance(
                message,
                str,
            ):
                marker = message.find(
                    "http"
                )

                if marker >= 0:
                    source_url = message[
                        marker:
                    ].strip()

            event_kind = (
                PresentationEventType.SOURCE
                if source_url
                else PresentationEventType.ACTIVITY
            )

            return [
                GideonPresentationEvent(
                    type=event_kind,
                    state=state,
                    phase="research",
                    title=title,
                    detail=(
                        str(message)
                        if message
                        else None
                    ),
                    run_id=run_id,
                    tool=(
                        str(tool)
                        if tool
                        else None
                    ),
                    source_url=source_url,
                )
            ]

        # ----------------------------------------------------------
        # Scratchpad lifecycle.
        #
        # Never expose the raw entry. We only derive a semantic
        # activity label from its documented strategy prefix.
        # ----------------------------------------------------------

        if event_type == "scratchpad_status":
            entry = payload.get(
                "entry"
            )

            title = "Updating research notes"

            if isinstance(
                entry,
                str,
            ):
                for prefix, label in SCRATCHPAD_TITLES.items():
                    if entry.startswith(
                        prefix
                    ):
                        title = label
                        break

            return [
                GideonPresentationEvent(
                    type=PresentationEventType.ACTIVITY,
                    state=_normalise_state(
                        payload.get(
                            "state"
                        )
                    ),
                    phase="research",
                    title=title,
                    detail=payload.get(
                        "activity"
                    ),
                    run_id=run_id,
                    tool=payload.get(
                        "tool"
                    ),
                    assistant_id=payload.get(
                        "assistant_id"
                    ),
                    meta_data={
                        "operation": payload.get(
                            "operation"
                        ),
                    },
                )
            ]

        # ----------------------------------------------------------
        # Tool-call lifecycle.
        # ----------------------------------------------------------

        if event_type in {
            "tool_call_start",
            "tool_call_manifest",
        }:
            tool = payload.get(
                "tool"
            )

            return [
                GideonPresentationEvent(
                    type=PresentationEventType.ACTIVITY,
                    state=PresentationState.IN_PROGRESS,
                    title=(
                        f"Using {tool}"
                        if tool
                        else "Using a capability"
                    ),
                    phase="execution",
                    run_id=run_id,
                    tool=(
                        str(tool)
                        if tool
                        else None
                    ),
                )
            ]

        # ----------------------------------------------------------
        # Generated artifacts.
        # ----------------------------------------------------------

        if event_type in {
            "generated_file",
            "code_interpreter_file",
        }:
            filename = payload.get(
                "filename"
            )

            return [
                GideonPresentationEvent(
                    type=PresentationEventType.ARTIFACT,
                    state=PresentationState.SUCCESS,
                    phase="execution",
                    title=(
                        f"Created {filename}"
                        if filename
                        else "Created an artifact"
                    ),
                    run_id=run_id,
                    source_url=payload.get(
                        "url"
                    ),
                    meta_data={
                        "file_id": payload.get(
                            "file_id"
                        ),
                        "mime_type": payload.get(
                            "mime_type"
                        ),
                    },
                )
            ]

        # ----------------------------------------------------------
        # Terminal error.
        # ----------------------------------------------------------

        if event_type == "error":
            return [
                GideonPresentationEvent(
                    type=PresentationEventType.ATTENTION,
                    state=PresentationState.ERROR,
                    title="The task encountered an error",
                    detail=payload.get(
                        "error"
                    ),
                    run_id=run_id,
                )
            ]

        # ----------------------------------------------------------
        # Generic status fallback.
        # ----------------------------------------------------------

        if event_type == "status":
            tool = payload.get(
                "tool"
            )

            message = payload.get(
                "message"
            )

            return [
                GideonPresentationEvent(
                    type=PresentationEventType.ACTIVITY,
                    state=_normalise_state(
                        payload.get(
                            "status"
                        )
                    ),
                    phase="execution",
                    title=(
                        str(message)
                        if message
                        else (
                            f"Running {tool}"
                            if tool
                            else "Working"
                        )
                    ),
                    run_id=run_id,
                    tool=(
                        str(tool)
                        if tool
                        else None
                    ),
                )
            ]

        return []

    def final(
        self,
        *,
        run_id: str,
    ) -> GideonPresentationEvent:
        return GideonPresentationEvent(
            type=PresentationEventType.FINAL,
            state=PresentationState.SUCCESS,
            phase="response",
            title="Finished",
            run_id=run_id,
        )
