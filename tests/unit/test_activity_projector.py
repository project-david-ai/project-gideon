from project_gideon.integrations.project_david.activity_projector import (
    ActivityProjector,
)
from project_gideon.models.presentation import (
    PresentationEventType,
    PresentationState,
)


def test_research_status_becomes_phase_event():
    projector = ActivityProjector()

    events = projector.project(
        {
            "type": "research_status",
            "run_id": "run-1",
            "tool": "delegate_research_task",
            "state": "in_progress",
            "activity": "Worker active. Streaming...",
        }
    )

    assert len(events) == 1

    event = events[0]

    assert event.type is PresentationEventType.PHASE
    assert event.state is PresentationState.IN_PROGRESS
    assert event.phase == "research"
    assert event.title == "Worker active. Streaming..."


def test_web_status_becomes_source_activity():
    projector = ActivityProjector()

    events = projector.project(
        {
            "type": "web_status",
            "run_id": "run-1",
            "status": "running",
            "tool": "read_web_page",
            "message": "Reading: https://example.com/page",
        }
    )

    event = events[0]

    assert event.type is PresentationEventType.SOURCE
    assert event.title == "Reading a source"
    assert event.source_url == "https://example.com/page"


def test_web_warning_is_not_terminal_error():
    projector = ActivityProjector()

    event = projector.project(
        {
            "type": "web_status",
            "run_id": "run-1",
            "status": "warning",
            "tool": "perform_web_search",
            "message": "No useful results; trying another path.",
        }
    )[0]

    assert event.state is PresentationState.WARNING
    assert event.type is PresentationEventType.ACTIVITY


def test_reasoning_is_not_projected():
    projector = ActivityProjector()

    assert (
        projector.project(
            {
                "type": "reasoning",
                "run_id": "run-1",
                "content": "internal reasoning",
            }
        )
        == []
    )


def test_raw_scratchpad_entry_is_not_exposed():
    projector = ActivityProjector()

    event = projector.project(
        {
            "type": "scratchpad_status",
            "run_id": "run-1",
            "operation": "append",
            "state": "success",
            "tool": "append_scratchpad",
            "activity": "Appending to scratchpad...",
            "entry": "✅ SECRET INTERNAL WORKING TEXT",
            "assistant_id": "worker-1",
        }
    )[0]

    assert event.title == "Completed a research step"

    serialized = event.model_dump_json()

    assert "SECRET INTERNAL WORKING TEXT" not in serialized


def test_generated_file_becomes_artifact():
    projector = ActivityProjector()

    event = projector.project(
        {
            "type": "generated_file",
            "run_id": "run-1",
            "filename": "report.pdf",
            "mime_type": "application/pdf",
            "file_id": "file-1",
            "url": "https://example.com/report.pdf",
        }
    )[0]

    assert event.type is PresentationEventType.ARTIFACT
    assert event.state is PresentationState.SUCCESS
    assert event.title == "Created report.pdf"


def test_final_event_is_explicit():
    projector = ActivityProjector()

    event = projector.final(
        run_id="run-1"
    )

    assert event.type is PresentationEventType.FINAL
    assert event.state is PresentationState.SUCCESS
    assert event.title == "Finished"
