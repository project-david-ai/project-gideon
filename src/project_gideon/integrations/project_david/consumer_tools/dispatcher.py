from __future__ import annotations

from collections.abc import Callable
from typing import Any


ConsumerToolHandler = Callable[
    [str, dict[str, Any]],
    str,
]


class UnknownConsumerTool(RuntimeError):
    pass


class DuplicateConsumerTool(RuntimeError):
    pass


class ConsumerToolDispatcher:
    """
    Registry for Gideon-owned consumer-side Project David function tools.

    The dispatcher does not manipulate Project David actions directly.
    ToolCallRequestEvent.execute() owns action lifecycle, tool-output
    submission and continuation into the next model turn.
    """

    def __init__(self) -> None:
        self._handlers: dict[
            str,
            ConsumerToolHandler,
        ] = {}

    def register(
        self,
        tool_name: str,
        handler: ConsumerToolHandler,
    ) -> None:
        if tool_name in self._handlers:
            raise DuplicateConsumerTool(
                f"Consumer tool already registered: {tool_name}"
            )

        self._handlers[tool_name] = handler

    def names(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                self._handlers
            )
        )

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        handler = self._handlers.get(
            tool_name
        )

        if handler is None:
            raise UnknownConsumerTool(
                f"No Gideon consumer handler registered for "
                f"tool={tool_name!r}."
            )

        return handler(
            tool_name,
            arguments,
        )

    def execute_event(
        self,
        event,
    ) -> bool:
        """
        Execute through Project David's public consumer-side API.

        This intentionally delegates action status, tool_call_id binding,
        tool-message submission and Turn N continuation to the SDK.
        """

        if event.tool_name not in self._handlers:
            raise UnknownConsumerTool(
                f"No Gideon consumer handler registered for "
                f"tool={event.tool_name!r}."
            )

        return event.execute(
            self.dispatch
        )