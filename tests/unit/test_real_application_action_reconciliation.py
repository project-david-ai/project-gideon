from dataclasses import dataclass

from project_gideon.integrations.project_david.action_reconciliation import (
    reconcile_failed_actions,
)


@dataclass
class Action:
    id: str
    tool_name: str
    triggered_at: str
    function_args: dict


def action(
    id_,
    tool,
    at,
    **args,
):
    return Action(
        id=id_,
        tool_name=tool,
        triggered_at=at,
        function_args=args,
    )


def test_unresolved_inspector_failure_is_deferred():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e122"},
    )

    assert result.recovered == ()
    assert result.deferred == (failed,)
    assert result.fatal == ()


def test_unresolved_selector_failure_is_deferred():
    failed = action(
        "f1",
        "playwright-primary__browser_select_combobox_option",
        "2026-10-05T13:00:00",
        target="f5e122",
        exactOption="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e122"},
    )

    assert result.deferred == (failed,)
    assert result.fatal == ()


def test_same_failure_is_fatal_for_ready_for_review():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.deferred == ()
    assert result.fatal == (failed,)


def test_failure_for_different_unresolved_field_is_fatal():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e138"},
    )

    assert result.deferred == ()
    assert result.fatal == (failed,)


def test_later_exact_inspector_retry_recovers():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:05",
        target="f5e122",
        query="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="needs_input",
        unresolved_field_ids={"f5e122"},
    )

    assert result.recovered == (failed,)
    assert result.deferred == ()
    assert result.fatal == ()


def test_earlier_success_does_not_recover_later_failure():
    completed = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T12:59:59",
        target="f5e122",
        query="BPP University",
    )

    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_different_query_does_not_recover_inspector_failure():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:00",
        target="f5e122",
        query="BPP University",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T13:00:05",
        target="f5e122",
        query="Another University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_exact_selector_recovery_requires_same_option():
    failed = action(
        "f1",
        "playwright-primary__browser_select_combobox_option",
        "2026-10-05T13:00:00",
        target="f5e48",
        exactOption="United Kingdom +44",
    )

    wrong = action(
        "c1",
        "playwright-primary__browser_select_combobox_option",
        "2026-10-05T13:00:05",
        target="f5e48",
        exactOption="Argentina +54",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[wrong],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_upload_recovery_uses_staged_path_not_stale_dom_ref():
    failed = action(
        "f1",
        "playwright-primary__browser_upload_candidate_file",
        "2026-10-05T13:00:00",
        target="f5e73",
        path="/uploads/candidate-cv.docx",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_upload_candidate_file",
        "2026-10-05T13:00:10",
        target="f9e99",
        path="/uploads/candidate-cv.docx",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == (failed,)
    assert result.fatal == ()


def test_failed_snapshot_is_recovered_by_later_snapshot():
    failed = action(
        "f1",
        "playwright-primary__browser_snapshot",
        "2026-10-05T13:00:00",
        target="f5e73",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_snapshot",
        "2026-10-05T13:00:03",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result.recovered == (failed,)
    assert result.fatal == ()


def test_application_prepare_requires_later_application_prepare():
    failed = action(
        "f1",
        "application_prepare",
        "2026-10-05T13:00:00",
        application_id="app_1",
    )

    unrelated = action(
        "c1",
        "playwright-primary__browser_snapshot",
        "2026-10-05T13:00:02",
    )

    recovered = action(
        "c2",
        "application_prepare",
        "2026-10-05T13:00:05",
        application_id="app_1",
    )

    result_without_recovery = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[unrelated],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result_without_recovery.fatal == (failed,)

    result_with_recovery = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[
            unrelated,
            recovered,
        ],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result_with_recovery.recovered == (failed,)
    assert result_with_recovery.fatal == ()


def test_broad_fill_failure_cannot_hide_behind_needs_input():
    failed = action(
        "f1",
        "playwright-primary__browser_fill_form",
        "2026-10-05T13:00:00",
        target="f5e122",
        fields=[
            {
                "name": "School",
                "value": "BPP University",
            }
        ],
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e122"},
    )

    assert result.deferred == ()
    assert result.fatal == (failed,)


def test_upload_failure_cannot_hide_behind_needs_input():
    failed = action(
        "f1",
        "playwright-primary__browser_upload_candidate_file",
        "2026-10-05T13:00:00",
        target="f5e73",
        path="/uploads/candidate-cv.docx",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e73"},
    )

    assert result.deferred == ()
    assert result.fatal == (failed,)


def test_forbidden_generic_browser_action_is_fatal():
    failed = action(
        "f1",
        "playwright-primary__browser_click",
        "2026-10-05T13:00:00",
        target="f5e122",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[],
        final_state="needs_input",
        unresolved_field_ids={"f5e122"},
    )

    assert result.deferred == ()
    assert result.fatal == (failed,)


def test_inspector_recovery_allows_ref_refresh_for_same_semantic_element():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T16:59:40",
        target="f5e161",
        element="Country of residence combobox",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T17:00:17",
        target="f5e158",
        element="Country of residence combobox",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result.recovered == (failed,)
    assert result.fatal == ()


def test_inspector_ref_refresh_does_not_cross_semantic_elements():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T16:59:40",
        target="f5e161",
        element="Country of residence combobox",
    )

    completed = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T17:00:17",
        target="f5e158",
        element="School combobox",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_inspector_ref_refresh_preserves_query_when_present():
    failed = action(
        "f1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T16:59:40",
        target="old",
        element="School combobox",
        query="BPP University",
    )

    wrong_query = action(
        "c1",
        "playwright-primary__browser_inspect_combobox_options",
        "2026-10-05T17:00:17",
        target="new",
        element="School combobox",
        query="Another University",
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[wrong_query],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_failed_legacy_file_search_recovers_via_related_query_text():
    failed = action(
        "f1",
        "file_search",
        "2026-10-05T16:55:35",
        query=(
            "Francis Neequaye CV senior backend software engineer "
            "LLM integration automation skills experience"
        ),
        top_k=10,
    )

    completed = action(
        "c1",
        "file_search",
        "2026-10-05T16:55:49",
        query_text=(
            "Francis Neequaye CV senior backend software engineer "
            "LLM integration and automation skills experience"
        ),
        top_k=10,
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result.recovered == (failed,)
    assert result.fatal == ()


def test_failed_legacy_file_search_can_recover_from_related_refinement():
    failed = action(
        "f1",
        "file_search",
        "2026-10-05T16:55:43",
        query=(
            "Francis Neequaye CV backend engineering experience "
            "Python distributed systems data infrastructure"
        ),
        top_k=10,
    )

    completed = action(
        "c1",
        "file_search",
        "2026-10-05T16:55:49",
        query_text=(
            "Francis Neequaye CV senior backend software engineer "
            "LLM integration and automation skills experience"
        ),
        top_k=10,
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="needs_input",
        unresolved_field_ids=set(),
    )

    assert result.recovered == (failed,)
    assert result.fatal == ()


def test_unrelated_later_file_search_does_not_recover_failure():
    failed = action(
        "f1",
        "file_search",
        "2026-10-05T16:55:43",
        query=(
            "Francis Neequaye CV backend engineering experience "
            "Python distributed systems data infrastructure"
        ),
        top_k=10,
    )

    completed = action(
        "c1",
        "file_search",
        "2026-10-05T16:55:49",
        query_text=(
            "completely unrelated cooking recipes "
            "Italian pasta tomatoes cheese"
        ),
        top_k=10,
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)


def test_file_search_success_before_failure_does_not_recover():
    completed = action(
        "c1",
        "file_search",
        "2026-10-05T16:55:30",
        query_text=(
            "Francis Neequaye CV senior backend software engineer"
        ),
        top_k=10,
    )

    failed = action(
        "f1",
        "file_search",
        "2026-10-05T16:55:35",
        query=(
            "Francis Neequaye CV senior backend software engineer"
        ),
        top_k=10,
    )

    result = reconcile_failed_actions(
        failed_actions=[failed],
        completed_actions=[completed],
        final_state="ready_for_review",
        unresolved_field_ids=set(),
    )

    assert result.recovered == ()
    assert result.fatal == (failed,)
