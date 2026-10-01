from __future__ import annotations

import hashlib
import re

from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIdentity,
    JobIngestionCandidate,
)


_SPACE_RE = re.compile(
    r"\s+"
)

_NON_WORD_RE = re.compile(
    r"[^a-z0-9]+"
)


def _normalise_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    value = value.strip().lower()

    value = _SPACE_RE.sub(
        " ",
        value,
    )

    return value


def _normalise_token(
    value: str | None,
) -> str:
    value = _normalise_text(
        value
    )

    return _NON_WORD_RE.sub(
        "",
        value,
    )


def canonical_job_fingerprint(
    job: Job,
) -> str:
    """
    Stable deterministic cross-source fingerprint.

    This intentionally uses conservative structured fields only.
    Description text is excluded because boards frequently rewrite or
    truncate descriptions independently.
    """

    material = "|".join(
        (
            _normalise_token(
                job.company
            ),
            _normalise_token(
                job.title
            ),
            _normalise_token(
                job.location
            ),
            "remote"
            if job.remote is True
            else (
                "onsite"
                if job.remote is False
                else "unknown"
            ),
            _normalise_token(
                job.employment_type
            ),
        )
    )

    return hashlib.sha256(
        material.encode(
            "utf-8"
        )
    ).hexdigest()


def build_job_identity(
    candidate: JobIngestionCandidate,
) -> JobIdentity:
    job = candidate.job

    return JobIdentity(
        tenant_id=job.tenant_id,
        source=_normalise_text(
            job.source
        ),
        source_job_id=(
            _normalise_text(
                job.source_job_id
            )
            or None
        ),
        requisition_id=(
            _normalise_text(
                candidate.requisition_id
            )
            or None
        ),
        canonical_fingerprint=canonical_job_fingerprint(
            job
        ),
    )
