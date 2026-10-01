from project_gideon.models.session import (
    SupervisorToolCallRecord,
    SupervisorTurnResult,
)


def test_supervisor_turn_result_is_typed_user_visible_contract():
    result = SupervisorTurnResult(
        assistant_id="assistant-1",
        thread_id="thread-1",
        message_id="message-1",
        run_id="run-1",
        content="Final answer.",
        tool_calls=[
            SupervisorToolCallRecord(
                tool_name="research_delegate",
                arguments={
                    "tenant_id": "tenant-1",
                    "objective": "Research Acme.",
                },
                executed=True,
            )
        ],
        meta_data={
            "gideon_faction": "career",
        },
    )

    assert result.content == "Final answer."
    assert result.tool_calls[0].tool_name == "research_delegate"
    assert result.tool_calls[0].executed is True
