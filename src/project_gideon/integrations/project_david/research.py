from __future__ import annotations

from collections.abc import Callable

import json
import os
from datetime import datetime, timezone
from typing import Any

from projectdavid import ContentEvent

from project_gideon.models.presentation import (
    GideonPresentationEvent,
)
from project_gideon.integrations.project_david.activity_projector import (
    ActivityProjector,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    ResearchDelegationRequest,
    ResearchDelegationResult,
    ResearchSource,
)


RESEARCH_ASSISTANT_NAME = "gideon-research-supervisor"

RESEARCH_ASSISTANT_INSTRUCTIONS = """
You are Gideon's dedicated research supervisor.

You receive bounded research objectives from Gideon's career supervisor.

Own research decomposition and evidence gathering inside this research
faction. Use Project David deep-research orchestration and web capabilities
where appropriate.

Return a concise but sufficiently complete research report. Preserve source
URLs or citations whenever available.

Do not mutate Gideon's canonical job, application, candidate, approval, or
workflow state. You return knowledge and provenance only.
""".strip()


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class ProjectDavidResearchDelegationPort:
    """
    Research-faction adapter implemented entirely through Project David's
    public SDK.

    Every delegation receives its own bounded thread/run. The dedicated
    research assistant owns deep-research behaviour; the calling Gideon
    supervisor never becomes a research worker or supervisor.
    """

    def __init__(
        self,
        *,
        client_factory,
        model: str,
        provider_api_key: str | None = None,
        assistant_name: str = RESEARCH_ASSISTANT_NAME,
        max_turns: int = 20,
    ) -> None:
        """
        Research owns an isolated Project David Entity instance.

        SynchronousInferenceStream is stateful. Reusing the career
        supervisor's Entity during a nested research_delegate call would
        overwrite the outer stream's thread/run/assistant state.
        """

        self._client_factory = client_factory
        self._client = None
        self._model = model
        self._provider_api_key = provider_api_key
        self._assistant_name = assistant_name
        self._max_turns = max_turns

    def bind_presentation(
        self,
        *,
        presentation_sink: Callable[
            [GideonPresentationEvent],
            None,
        ]
        | None,
        activity_projector: ActivityProjector | None = None,
    ) -> None:
        """
        Bind the research faction to Gideon's portable presentation stream.

        The research Entity remains isolated. Only projected semantic activity
        crosses the faction boundary.
        """

        self._presentation_sink = presentation_sink

        self._activity_projector = (
            activity_projector
            or ActivityProjector()
        )

    def _relay_presentation_event(
        self,
        event,
    ) -> None:
        sink = getattr(
            self,
            "_presentation_sink",
            None,
        )

        if sink is None:
            return

        projector = getattr(
            self,
            "_activity_projector",
            None,
        )

        if projector is None:
            projector = ActivityProjector()

            self._activity_projector = projector

        for presentation_event in projector.project(
            event
        ):
            if presentation_event.faction is None:
                presentation_event = (
                    presentation_event.model_copy(
                        update={
                            "faction": "research",
                        }
                    )
                )

            sink(
                presentation_event
            )

    def _get_client(
        self,
    ):
        if self._client is None:
            self._client = self._client_factory()

        return self._client

    def _ensure_research_assistant(
        self,
    ):
        client = self._get_client()

        matches = [
            assistant
            for assistant in client.assistants.list_assistants()
            if getattr(
                assistant,
                "name",
                None,
            ) == self._assistant_name
        ]

        if len(matches) > 1:
            raise RuntimeError(
                "Multiple Project David research assistants exist with "
                f"logical name={self._assistant_name!r}."
            )

        updates = {
            "name": self._assistant_name,
            "model": self._model,
            "instructions": RESEARCH_ASSISTANT_INSTRUCTIONS,
            "tools": [
                {
                    "type": "web_search",
                }
            ],
            "agent_mode": True,
            "web_access": True,
            "deep_research": True,
            "max_turns": self._max_turns,
        }

        if matches:
            assistant = matches[0]

            return client.assistants.update_assistant(
                assistant_id=assistant.id,
                **updates,
            )

        return client.assistants.create_assistant(
            **updates,
        )

    @staticmethod
    def _build_prompt(
        request: ResearchDelegationRequest,
    ) -> str:
        payload = {
            "objective": request.objective,
            "context": request.context,
        }

        if request.max_depth is not None:
            payload["max_depth"] = request.max_depth

        return (
            "Execute this bounded Gideon research delegation.\n\n"
            + json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    @staticmethod
    def _extract_sources(
        events: list[Any],
    ) -> list[ResearchSource]:
        """
        Preserve source-like structured data emitted by Project David when
        present without inventing provenance.

        Unknown event shapes are ignored rather than guessed.
        """

        sources: list[ResearchSource] = []
        seen: set[tuple[str | None, str | None]] = set()

        for event in events:
            try:
                payload = event.to_dict()
            except Exception:
                continue

            candidates: list[Any] = []

            for key in (
                "sources",
                "citations",
                "references",
            ):
                value = payload.get(
                    key
                )

                if isinstance(
                    value,
                    list,
                ):
                    candidates.extend(
                        value
                    )

            for candidate in candidates:
                if isinstance(
                    candidate,
                    str,
                ):
                    url = (
                        candidate
                        if candidate.startswith(
                            (
                                "http://",
                                "https://",
                            )
                        )
                        else None
                    )

                    citation = (
                        None
                        if url
                        else candidate
                    )

                    key = (
                        url,
                        citation,
                    )

                    if key in seen:
                        continue

                    seen.add(key)

                    sources.append(
                        ResearchSource(
                            url=url,
                            citation=citation,
                        )
                    )

                    continue

                if not isinstance(
                    candidate,
                    dict,
                ):
                    continue

                url = (
                    candidate.get("url")
                    or candidate.get("href")
                )

                title = candidate.get(
                    "title"
                )

                citation = (
                    candidate.get("citation")
                    or candidate.get("text")
                )

                meta_data = {
                    key: value
                    for key, value in candidate.items()
                    if key not in {
                        "url",
                        "href",
                        "title",
                        "citation",
                        "text",
                    }
                }

                if not any(
                    (
                        url,
                        title,
                        citation,
                        meta_data,
                    )
                ):
                    continue

                dedupe_key = (
                    url,
                    citation,
                )

                if dedupe_key in seen:
                    continue

                seen.add(
                    dedupe_key
                )

                sources.append(
                    ResearchSource(
                        title=title,
                        url=url,
                        citation=citation,
                        meta_data=meta_data,
                    )
                )

        return sources

    def delegate_research(
        self,
        request: ResearchDelegationRequest,
    ) -> ResearchDelegationResult:
        started_at = utc_now()

        client = self._get_client()
        assistant = self._ensure_research_assistant()

        thread = client.threads.create_thread(
            meta_data={
                "gideon_faction": "research",
                "gideon_tenant_id": request.tenant_id,
            }
        )

        message = client.messages.create_message(
            thread_id=thread.id,
            role="user",
            content=self._build_prompt(
                request
            ),
            assistant_id=assistant.id,
            meta_data={
                "gideon_delegation": "research",
                "gideon_tenant_id": request.tenant_id,
            },
        )

        run = client.runs.create_run(
            assistant_id=assistant.id,
            thread_id=thread.id,
            meta_data={
                "gideon_faction": "research",
                "gideon_tenant_id": request.tenant_id,
            },
        )

        stream = client.synchronous_inference_stream

        stream.bind_clients(
            client.runs,
            client.actions,
            client.messages,
            client.assistants,
        )

        stream.setup(
            thread_id=thread.id,
            assistant_id=assistant.id,
            message_id=message.id,
            run_id=run.id,
            api_key=self._provider_api_key,
            meta_data={
                "gideon_faction": "research",
                "gideon_tenant_id": request.tenant_id,
            },
        )

        events: list[Any] = []
        content_parts: list[str] = []

        try:
            for event in stream.stream_events(
                model=self._model,
                max_turns=self._max_turns,
            ):
                self._relay_presentation_event(
                    event
                )

                events.append(
                    event
                )

                if isinstance(
                    event,
                    ContentEvent,
                ):
                    payload = event.to_dict()

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

            report = "".join(
                content_parts
            ).strip()

            if not report:
                raise RuntimeError(
                    "Research faction completed without a report."
                )

            return ResearchDelegationResult(
                status=DelegationStatus.SUCCEEDED,
                report=report,
                sources=self._extract_sources(
                    events
                ),
                research_run_id=run.id,
                thread_id=thread.id,
                started_at=started_at,
                completed_at=utc_now(),
                meta_data={
                    "assistant_id": assistant.id,
                    "assistant_name": self._assistant_name,
                    "deep_research": True,
                    "web_access": True,
                },
            )

        except Exception as exc:
            return ResearchDelegationResult(
                status=DelegationStatus.FAILED,
                error=str(exc),
                research_run_id=run.id,
                thread_id=thread.id,
                started_at=started_at,
                completed_at=utc_now(),
                meta_data={
                    "assistant_id": assistant.id,
                    "assistant_name": self._assistant_name,
                },
            )


def resolve_provider_api_key() -> str | None:
    """
    Deployment-level provider credential.

    Gideon does not hard-code a provider. A canonical override may be supplied;
    common local Project David provider variables remain compatible.
    """

    for name in (
        "GIDEON_PROVIDER_API_KEY",
        "TOGETHER_API_KEY",
        "HYPERBOLIC_API_KEY",
        "OPENAI_API_KEY",
    ):
        value = os.getenv(
            name
        )

        if value:
            return value

    return None