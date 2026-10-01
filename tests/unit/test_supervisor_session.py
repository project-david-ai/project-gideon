from types import SimpleNamespace

import pytest

import project_gideon.integrations.project_david.supervisor_session as session_module
from project_gideon.integrations.project_david.consumer_tools.dispatcher import (
    ConsumerToolDispatcher,
)
from project_gideon.integrations.project_david.supervisor_session import (
    SupervisorSessionError,
    SupervisorSessionService,
)


class FakeToolCallEvent:
    def __init__(
        self,
        *,
        tool_name,
        args,
    ):
        self.tool_name = tool_name
        self.args = args
        self.action_id = "action-1"
        self.tool_call_id = "call-1"
        self.executed = False

    def execute(
        self,
        executor,
    ):
        result = executor(
            self.tool_name,
            self.args,
        )

        assert isinstance(
            result,
            str,
        )

        self.executed = True
        return True


class FakeContentEvent:
    def __init__(
        self,
        content,
    ):
        self._content = content

    def to_dict(
        self,
    ):
        return {
            "content": self._content,
        }


class FakeThreads:
    def __init__(self):
        self.calls = []

    def create_thread(
        self,
        *,
        meta_data,
    ):
        self.calls.append(
            meta_data
        )

        return SimpleNamespace(
            id="thread-1"
        )


class FakeMessages:
    def __init__(self):
        self.calls = []

    def create_message(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        return SimpleNamespace(
            id="message-1"
        )


class FakeRuns:
    def __init__(self):
        self.calls = []

    def create_run(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        return SimpleNamespace(
            id="run-1"
        )


class FakeStream:
    def __init__(
        self,
        events,
    ):
        self.events = list(
            events
        )

        self.bound = None
        self.setup_kwargs = None
        self.stream_kwargs = None

    def bind_clients(
        self,
        *clients,
    ):
        self.bound = clients

    def setup(
        self,
        **kwargs,
    ):
        self.setup_kwargs = kwargs

    def stream_events(
        self,
        model,
        *,
        max_turns,
    ):
        self.stream_kwargs = {
            "model": model,
            "max_turns": max_turns,
        }

        yield from self.events


class FakeClient:
    def __init__(
        self,
        events,
    ):
        self.threads = FakeThreads()
        self.messages = FakeMessages()
        self.runs = FakeRuns()

        self.actions = object()
        self.assistants = object()

        self.synchronous_inference_stream = FakeStream(
            events
        )


def test_supervisor_session_dispatches_tool_and_returns_turn_n_content(
    monkeypatch,
):
    monkeypatch.setattr(
        session_module,
        "ToolCallRequestEvent",
        FakeToolCallEvent,
    )

    monkeypatch.setattr(
        session_module,
        "ContentEvent",
        FakeContentEvent,
    )

    tool_event = FakeToolCallEvent(
        tool_name="research_delegate",
        args={
            "tenant_id": "tenant-1",
            "objective": "Research Acme.",
        },
    )

    client = FakeClient(
        [
            tool_event,
            FakeContentEvent(
                "Turn "
            ),
            FakeContentEvent(
                "2 answer."
            ),
        ]
    )

    dispatcher = ConsumerToolDispatcher()
    observed = []

    def handler(
        tool_name,
        arguments,
    ):
        observed.append(
            (
                tool_name,
                arguments,
            )
        )

        return '{"status":"succeeded","report":"Evidence"}'

    dispatcher.register(
        "research_delegate",
        handler,
    )

    service = SupervisorSessionService(
        client=client,
        assistant_id="assistant-1",
        model="test-model",
        dispatcher=dispatcher,
        provider_api_key="provider-key",
        max_turns=7,
    )

    result = service.run(
        prompt="Research this.",
        meta_data={
            "tenant_id": "tenant-1",
            "gideon_faction": "attempted-override",
        },
    )

    assert result.content == "Turn 2 answer."

    assert result.thread_id == "thread-1"
    assert result.message_id == "message-1"
    assert result.run_id == "run-1"

    assert result.meta_data["tenant_id"] == "tenant-1"
    assert result.meta_data["gideon_faction"] == "career"

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].tool_name == "research_delegate"
    assert result.tool_calls[0].executed is True

    assert observed == [
        (
            "research_delegate",
            {
                "tenant_id": "tenant-1",
                "objective": "Research Acme.",
            },
        )
    ]

    assert tool_event.executed is True

    assert (
        client.synchronous_inference_stream.setup_kwargs[
            "assistant_id"
        ]
        == "assistant-1"
    )

    assert (
        client.synchronous_inference_stream.setup_kwargs[
            "api_key"
        ]
        == "provider-key"
    )

    assert (
        client.synchronous_inference_stream.stream_kwargs
        == {
            "model": "test-model",
            "max_turns": 7,
        }
    )


def test_supervisor_session_rejects_empty_prompt():
    service = SupervisorSessionService(
        client=FakeClient(
            []
        ),
        assistant_id="assistant-1",
        model="test-model",
        dispatcher=ConsumerToolDispatcher(),
    )

    with pytest.raises(
        SupervisorSessionError,
        match="must not be empty",
    ):
        service.run(
            prompt="   "
        )


def test_supervisor_session_requires_final_content():
    service = SupervisorSessionService(
        client=FakeClient(
            []
        ),
        assistant_id="assistant-1",
        model="test-model",
        dispatcher=ConsumerToolDispatcher(),
    )

    with pytest.raises(
        SupervisorSessionError,
        match="without user-visible content",
    ):
        service.run(
            prompt="Hello."
        )


def test_supervisor_session_emits_portable_presentation_events(
    monkeypatch,
):
    monkeypatch.setattr(
        session_module,
        "ContentEvent",
        FakeContentEvent,
    )

    class FakeStatusEvent:
        def to_dict(
            self,
        ):
            return {
                "type": "web_status",
                "run_id": "run-1",
                "status": "running",
                "tool": "read_web_page",
                "message": "Reading: https://example.com/source",
            }

    client = FakeClient(
        [
            FakeStatusEvent(),
            FakeContentEvent(
                "Finished response."
            ),
        ]
    )

    observed = []

    service = SupervisorSessionService(
        client=client,
        assistant_id="assistant-1",
        model="test-model",
        dispatcher=ConsumerToolDispatcher(),
        presentation_sink=observed.append,
    )

    result = service.run(
        prompt="Research this."
    )

    assert result.content == "Finished response."

    assert len(observed) == 2

    assert observed[0].title == "Reading a source"
    assert (
        observed[0].source_url
        == "https://example.com/source"
    )

    assert observed[1].type.value == "final"
    assert observed[1].title == "Finished"

