from __future__ import annotations

import hashlib
import hmac
import json
from typing import Mapping

from project_gideon.models.application import (
    JobApplication,
)


APPLICATION_REVIEW_FINGERPRINT_KEY = (
    "application_review_fingerprint"
)


class ApplicationReviewFingerprintError(ValueError):
    pass


def application_review_payload(
    application: JobApplication,
) -> dict[str, object]:
    """
    Canonical domain material presented for human approval.

    Workflow-only state and timestamps are intentionally excluded so
    READY_FOR_REVIEW -> APPROVED -> SUBMITTING does not itself stale
    the human approval.

    The future browser submission actuator must separately validate
    fresh browser evidence before pressing the external Submit control.
    """

    try:
        dumped = application.model_dump(
            mode="json"
        )
    except Exception as exc:
        raise ApplicationReviewFingerprintError(
            "Application review material is not JSON serializable."
        ) from exc

    meta_data = dict(
        dumped.get(
            "meta_data",
            {},
        )
    )

    # Result metadata is produced after authority has already crossed
    # the submission boundary and is therefore not review content.
    meta_data.pop(
        "submission",
        None,
    )

    return {
        "application_id":
            dumped["id"],

        "tenant_id":
            dumped["tenant_id"],

        "job_id":
            dumped["job_id"],

        "candidate_id":
            dumped["candidate_id"],

        "browser_session_id":
            dumped.get(
                "browser_session_id"
            ),

        "cv_file_id":
            dumped.get(
                "cv_file_id"
            ),

        "cover_letter_file_id":
            dumped.get(
                "cover_letter_file_id"
            ),

        "unresolved_questions":
            dumped.get(
                "unresolved_questions",
                [],
            ),

        "meta_data":
            meta_data,
    }


def application_review_fingerprint(
    application: JobApplication,
) -> str:
    payload = application_review_payload(
        application
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    ).encode(
        "utf-8"
    )

    return hashlib.sha256(
        canonical
    ).hexdigest()


def bound_review_fingerprint(
    meta_data: Mapping[
        str,
        object,
    ],
) -> str | None:
    value = meta_data.get(
        APPLICATION_REVIEW_FINGERPRINT_KEY
    )

    if not isinstance(
        value,
        str,
    ):
        return None

    value = value.strip()

    if not value:
        return None

    return value


def review_binding_matches(
    *,
    application: JobApplication,
    meta_data: Mapping[
        str,
        object,
    ],
) -> bool:
    expected = bound_review_fingerprint(
        meta_data
    )

    if expected is None:
        return False

    current = application_review_fingerprint(
        application
    )

    return hmac.compare_digest(
        expected,
        current,
    )
