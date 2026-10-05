from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HARNESS = (
    ROOT
    / "scripts"
    / "live_real_application_prepare.py"
)

RECONCILER = (
    ROOT
    / "src"
    / "project_gideon"
    / "integrations"
    / "project_david"
    / "action_reconciliation.py"
)


def test_real_harness_uses_reconciled_failure_contract():
    value = HARNESS.read_text(
        encoding="utf-8"
    )

    assert (
        "reconcile_failed_actions"
        in value
    )

    assert (
        "RECOVERED_FAILED_ACTIONS="
        in value
    )

    assert (
        "DEFERRED_FAILED_ACTIONS="
        in value
    )

    assert (
        "UNRECONCILED_FATAL_ACTIONS="
        in value
    )

    assert (
        "One or more unreconciled fatal "
        in value
    )

    assert (
        "One or more Project David Actions failed."
        not in value
    )

    assert (
        "Run retained non-terminal Actions."
        in value
    )

    assert (
        "SAFETY FAILURE: application was submitted."
        in value
    )

    assert (
        "ApplicationState.READY_FOR_REVIEW"
        in value
    )

    assert (
        "ApplicationState.NEEDS_INPUT"
        in value
    )


def test_reconciliation_layer_is_conservative():
    value = RECONCILER.read_text(
        encoding="utf-8"
    )

    assert (
        "__browser_fill_form"
        not in value[
            value.index(
                "_DEFERABLE_BROWSER_SUFFIXES"
            ):
            value.index(
                "def _field"
            )
        ]
    )

    assert (
        "__browser_upload_candidate_file"
        not in value[
            value.index(
                "_DEFERABLE_BROWSER_SUFFIXES"
            ):
            value.index(
                "def _field"
            )
        ]
    )

    assert (
        "__browser_click"
        not in value[
            value.index(
                "_DEFERABLE_BROWSER_SUFFIXES"
            ):
            value.index(
                "def _field"
            )
        ]
    )
