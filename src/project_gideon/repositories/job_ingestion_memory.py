from __future__ import annotations

from copy import deepcopy

from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIdentity,
    JobMatchType,
    JobUpsertResult,
)
from project_gideon.services.job_identity import (
    canonical_job_fingerprint,
)


class InMemoryJobIngestionRepository:
    """
    Deterministic in-memory implementation of the authoritative ingestion
    contract.

    This adapter is intended for tests and local domain validation.
    """

    def __init__(
        self,
    ) -> None:
        self._jobs: dict[
            tuple[str, str],
            Job,
        ] = {}

        self._source_identity: dict[
            tuple[str, str, str],
            str,
        ] = {}

        self._requisition_identity: dict[
            tuple[str, str],
            str,
        ] = {}

        self._fingerprint_identity: dict[
            tuple[str, str],
            str | None,
        ] = {}

    async def upsert_job(
        self,
        *,
        identity: JobIdentity,
        candidate: Job,
    ) -> JobUpsertResult:
        tenant_id = identity.tenant_id

        if identity.source_job_id:
            source_key = (
                tenant_id,
                identity.source,
                identity.source_job_id,
            )

            existing_id = self._source_identity.get(
                source_key
            )

            if existing_id:
                return JobUpsertResult(
                    job=deepcopy(
                        self._jobs[
                            (
                                tenant_id,
                                existing_id,
                            )
                        ]
                    ),
                    match_type=JobMatchType.EXACT_SOURCE_MATCH,
                    created=False,
                )

        if identity.requisition_id:
            requisition_key = (
                tenant_id,
                identity.requisition_id,
            )

            existing_id = self._requisition_identity.get(
                requisition_key
            )

            if existing_id:
                return JobUpsertResult(
                    job=deepcopy(
                        self._jobs[
                            (
                                tenant_id,
                                existing_id,
                            )
                        ]
                    ),
                    match_type=JobMatchType.REQUISITION_MATCH,
                    created=False,
                )

        fingerprint_key = (
            tenant_id,
            identity.canonical_fingerprint,
        )

        fingerprint_known = (
            fingerprint_key
            in self._fingerprint_identity
        )

        existing_id = self._fingerprint_identity.get(
            fingerprint_key
        )

        fingerprint_is_ambiguous = (
            fingerprint_known
            and existing_id is None
        )

        same_source_distinct_native_ids = False

        if existing_id is not None:
            existing_job = self._jobs[
                (
                    tenant_id,
                    existing_id,
                )
            ]

            existing_source = (
                existing_job.source.strip().lower()
            )

            existing_source_job_id = (
                (
                    existing_job.source_job_id
                    or ""
                )
                .strip()
                .lower()
            )

            same_source_distinct_native_ids = bool(
                identity.source_job_id
                and existing_source_job_id
                and existing_source
                == identity.source
                and existing_source_job_id
                != identity.source_job_id
            )

            if not same_source_distinct_native_ids:
                return JobUpsertResult(
                    job=deepcopy(
                        existing_job
                    ),
                    match_type=JobMatchType.CANONICAL_STRONG_MATCH,
                    created=False,
                )

        stored = deepcopy(
            candidate
        )

        self._jobs[
            (
                tenant_id,
                stored.id,
            )
        ] = stored

        if identity.source_job_id:
            self._source_identity[
                (
                    tenant_id,
                    identity.source,
                    identity.source_job_id,
                )
            ] = stored.id

        if identity.requisition_id:
            self._requisition_identity[
                (
                    tenant_id,
                    identity.requisition_id,
                )
            ] = stored.id

        if (
            fingerprint_is_ambiguous
            or same_source_distinct_native_ids
        ):
            self._fingerprint_identity[
                fingerprint_key
            ] = None
        else:
            self._fingerprint_identity[
                fingerprint_key
            ] = stored.id

        return JobUpsertResult(
            job=deepcopy(
                stored
            ),
            match_type=JobMatchType.DISTINCT,
            created=True,
        )

    async def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> Job:
        return deepcopy(
            self._jobs[
                (
                    tenant_id,
                    job_id,
                )
            ]
        )

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> list[Job]:
        return [
            deepcopy(
                job
            )
            for (
                record_tenant_id,
                _,
            ), job in self._jobs.items()
            if record_tenant_id == tenant_id
        ]
