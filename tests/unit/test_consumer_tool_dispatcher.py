from types import SimpleNamespace

import pytest

from project_gideon.integrations.project_david.consumer_tools.dispatcher import (
    ConsumerToolDispatcher,
    DuplicateConsumerTool,
    UnknownConsumerTool,
)


def test_dispatcher_routes_registered_tool():
    dispatcher = ConsumerToolDispatcher()

    calls = []

    def handler(
        tool_name,
        arguments,
    ):
        calls.append(
            (
                tool_name,
                arguments,
            )
        )

        return '{"status":"ok"}'

    dispatcher.register(
        "research_delegate",
        handler,
    )

    result = dispatcher.dispatch(
        "research_delegate",
        {
            "objective": "Research Acme.",
        },
    )

    assert result == '{"status":"ok"}'

    assert calls == [
        (
            "research_delegate",
            {
                "objective": "Research Acme.",
            },
        )
    ]


def test_dispatcher_rejects_duplicate_registration():
    dispatcher = ConsumerToolDispatcher()

    dispatcher.register(
        "research_delegate",
        lambda name, args: "{}",
    )

    with pytest.raises(
        DuplicateConsumerTool,
    ):
        dispatcher.register(
            "research_delegate",
            lambda name, args: "{}",
        )


def test_dispatcher_rejects_unknown_tool():
    dispatcher = ConsumerToolDispatcher()

    with pytest.raises(
        UnknownConsumerTool,
    ):
        dispatcher.dispatch(
            "unknown",
            {},
        )


def test_dispatcher_executes_via_project_david_event_surface():
    dispatcher = ConsumerToolDispatcher()

    dispatcher.register(
        "research_delegate",
        lambda name, args: '{"ok":true}',
    )

    observed = {}

    class FakeEvent:
        tool_name = "research_delegate"

        def execute(
            self,
            executor,
        ):
            observed["result"] = executor(
                self.tool_name,
                {
                    "tenant_id": "tenant-1",
                    "objective": "Research Acme.",
                },
            )

            return True

    success = dispatcher.execute_event(
        FakeEvent()
    )

    assert success is True
    assert observed["result"] == '{"ok":true}'


def test_dispatcher_refuses_unknown_event_before_execute():
    dispatcher = ConsumerToolDispatcher()

    event = SimpleNamespace(
        tool_name="unknown",
    )

    with pytest.raises(
        UnknownConsumerTool,
    ):
        dispatcher.execute_event(
            event
        )