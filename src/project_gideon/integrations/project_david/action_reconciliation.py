from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class ActionReconciliation:
    """
    Classification of historical failed Project David actions.

    recovered:
        A later successful action demonstrably recovered the failed
        operation.

    deferred:
        A safe, field-scoped browser action failed for a field which
        the durable application explicitly surfaced as NEEDS_INPUT.

    fatal:
        No safe recovery or durable NEEDS_INPUT reconciliation exists.
    """

    recovered: tuple[Any, ...]
    deferred: tuple[Any, ...]
    fatal: tuple[Any, ...]


_DEFERABLE_BROWSER_SUFFIXES = (
    "__browser_inspect_combobox_options",
    "__browser_select_combobox_option",
    "__browser_find",
    "__browser_snapshot",
)


def _field(
    value: Any,
    name: str,
    default: Any = None,
) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)

    return getattr(
        value,
        name,
        default,
    )


def _args(action: Any) -> dict[str, Any]:
    value = _field(
        action,
        "function_args",
        {},
    )

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def _timestamp(action: Any) -> str:
    value = _field(
        action,
        "triggered_at",
    )

    if value is None:
        return ""

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def _is_later(
    completed: Any,
    failed: Any,
) -> bool:
    completed_at = _timestamp(
        completed
    )

    failed_at = _timestamp(
        failed
    )

    # Fail closed when ordering cannot be proven.
    if not completed_at or not failed_at:
        return False

    return completed_at > failed_at


def _same_exact_args(
    left: Any,
    right: Any,
) -> bool:
    return _args(left) == _args(right)


def _same_target(
    left: Any,
    right: Any,
) -> bool:
    left_target = _args(left).get(
        "target"
    )

    right_target = _args(right).get(
        "target"
    )

    return (
        bool(left_target)
        and left_target == right_target
    )


def _normalized_element(
    action: Any,
) -> str:
    """
    Stable semantic identity for a reviewed browser element.

    DOM refs are deliberately excluded because React/Greenhouse may
    replace a control and issue a fresh ref while preserving the same
    semantic element.
    """

    element = str(
        _args(action).get(
            "element",
            "",
        )
        or ""
    )

    return " ".join(
        element.lower().split()
    )


def _same_semantic_element(
    left: Any,
    right: Any,
) -> bool:
    left_element = _normalized_element(
        left
    )

    right_element = _normalized_element(
        right
    )

    return (
        bool(left_element)
        and left_element
        == right_element
    )


def _search_terms(
    value: Any,
) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            str(
                value
                or ""
            ).lower(),
        )
        if len(token) > 1
    }


def _related_search_text(
    left: Any,
    right: Any,
) -> bool:
    """
    Require substantial token overlap.

    This prevents an unrelated later file_search from laundering an
    earlier failed search merely because both use the same tool.
    """

    left_terms = _search_terms(
        left
    )

    right_terms = _search_terms(
        right
    )

    if not left_terms or not right_terms:
        return False

    overlap = len(
        left_terms
        & right_terms
    )

    denominator = min(
        len(left_terms),
        len(right_terms),
    )

    return (
        overlap / denominator
        >= 0.40
    )


def _later_success_recovers(
    failed: Any,
    completed: Any,
) -> bool:
    if not _is_later(
        completed,
        failed,
    ):
        return False

    failed_name = str(
        _field(
            failed,
            "tool_name",
            "",
        )
        or ""
    )

    completed_name = str(
        _field(
            completed,
            "tool_name",
            "",
        )
        or ""
    )

    if not failed_name:
        return False

    failed_args = _args(
        failed
    )

    completed_args = _args(
        completed
    )

    # --------------------------------------------------------
    # Snapshot is non-mutating browser evidence.
    #
    # A later successful snapshot proves that a transient/stale
    # snapshot failure did not leave browser observation broken.
    # --------------------------------------------------------

    if failed_name.endswith(
        "__browser_snapshot"
    ):
        return completed_name.endswith(
            "__browser_snapshot"
        )

    # --------------------------------------------------------
    # application_prepare is recovered only by a later
    # successful application_prepare.
    # --------------------------------------------------------

    if failed_name == "application_prepare":
        return (
            completed_name
            == "application_prepare"
        )

    # --------------------------------------------------------
    # Candidate upload may receive a fresh DOM ref after a
    # stale-ref failure. The staged path is the durable identity.
    # --------------------------------------------------------

    if failed_name.endswith(
        "__browser_upload_candidate_file"
    ):
        if not completed_name.endswith(
            "__browser_upload_candidate_file"
        ):
            return False

        failed_path = failed_args.get(
            "path"
        )

        completed_path = completed_args.get(
            "path"
        )

        return (
            bool(failed_path)
            and failed_path
            == completed_path
        )

    # --------------------------------------------------------
    # Search/inspection recovery must preserve the exact field
    # and, where supplied, the exact discovery candidate.
    # --------------------------------------------------------

    if failed_name.endswith(
        "__browser_inspect_combobox_options"
    ):
        if completed_name != failed_name:
            return False

        # A reviewed inspector is non-mutating. React/Greenhouse may
        # replace the control and therefore change its snapshot ref.
        # Recovery is valid only when either:
        #
        #   - the DOM ref is unchanged; or
        #   - the explicit semantic element label is unchanged.
        #
        # We never infer identity from proximity or fuzzy labels.
        same_identity = (
            _same_target(
                failed,
                completed,
            )
            or _same_semantic_element(
                failed,
                completed,
            )
        )

        if not same_identity:
            return False

        failed_query = failed_args.get(
            "query"
        )

        if failed_query is None:
            return True

        return (
            completed_args.get(
                "query"
            )
            == failed_query
        )

    # --------------------------------------------------------
    # Exact combobox selection recovery must preserve both the
    # field and the exact browser-observed option.
    # --------------------------------------------------------

    if failed_name.endswith(
        "__browser_select_combobox_option"
    ):
        return (
            completed_name
            == failed_name
            and _same_target(
                failed,
                completed,
            )
            and completed_args.get(
                "exactOption"
            )
            == failed_args.get(
                "exactOption"
            )
        )

    # --------------------------------------------------------
    # Browser find is field-scoped discovery. Require the same
    # target and same requested arguments.
    # --------------------------------------------------------

    if failed_name.endswith(
        "__browser_find"
    ):
        return (
            completed_name
            == failed_name
            and _same_target(
                failed,
                completed,
            )
            and _same_exact_args(
                failed,
                completed,
            )
        )

    # --------------------------------------------------------
    # file_search schema self-correction.
    #
    # Historical Project David Actions prove the model may first
    # emit the legacy/incorrect:
    #
    #     {"query": "..."}
    #
    # and then self-correct to:
    #
    #     {"query_text": "..."}
    #
    # A failed file_search is recoverable only when:
    #
    #   - a later file_search completed;
    #   - the failed call used query;
    #   - the successful call used query_text;
    #   - the two searches are substantially semantically related.
    #
    # This is read-only retrieval recovery, not mutation recovery.
    # --------------------------------------------------------

    if failed_name == "file_search":
        if completed_name != "file_search":
            return False

        failed_query = failed_args.get(
            "query"
        )

        completed_query = completed_args.get(
            "query_text"
        )

        return (
            bool(failed_query)
            and bool(completed_query)
            and _related_search_text(
                failed_query,
                completed_query,
            )
        )

    # --------------------------------------------------------
    # Everything else is deliberately conservative:
    #
    # - same tool,
    # - exact same args,
    # - later successful execution.
    #
    # Broad form fills, navigation, or any future action type
    # are NOT forgiven merely because something else succeeded.
    # --------------------------------------------------------

    return (
        completed_name
        == failed_name
        and _same_exact_args(
            failed,
            completed,
        )
    )


def _is_deferred_to_needs_input(
    action: Any,
    *,
    final_state: str,
    unresolved_field_ids: set[str],
) -> bool:
    if final_state != "needs_input":
        return False

    name = str(
        _field(
            action,
            "tool_name",
            "",
        )
        or ""
    )

    if not any(
        name.endswith(suffix)
        for suffix
        in _DEFERABLE_BROWSER_SUFFIXES
    ):
        return False

    target = _args(
        action
    ).get(
        "target"
    )

    return (
        isinstance(target, str)
        and target
        in unresolved_field_ids
    )


def reconcile_failed_actions(
    *,
    failed_actions: Iterable[Any],
    completed_actions: Iterable[Any],
    final_state: str,
    unresolved_field_ids: Iterable[str],
) -> ActionReconciliation:
    """
    Reconcile historical tool failures against the durable outcome.

    This function never converts a failure to success merely because
    the application reached a terminal state.

    A failed action is non-fatal only when:

    1. a later completed action proves recovery; or
    2. it is an explicitly approved field-scoped browser operation
       and that exact field is represented in durable NEEDS_INPUT.

    Everything else remains fatal.
    """

    failed = tuple(
        failed_actions
    )

    completed = tuple(
        completed_actions
    )

    unresolved = {
        str(value)
        for value
        in unresolved_field_ids
        if value
    }

    recovered: list[Any] = []
    deferred: list[Any] = []
    fatal: list[Any] = []

    for failed_action in failed:
        if any(
            _later_success_recovers(
                failed_action,
                completed_action,
            )
            for completed_action
            in completed
        ):
            recovered.append(
                failed_action
            )
            continue

        if _is_deferred_to_needs_input(
            failed_action,
            final_state=final_state,
            unresolved_field_ids=unresolved,
        ):
            deferred.append(
                failed_action
            )
            continue

        fatal.append(
            failed_action
        )

    return ActionReconciliation(
        recovered=tuple(
            recovered
        ),
        deferred=tuple(
            deferred
        ),
        fatal=tuple(
            fatal
        ),
    )
