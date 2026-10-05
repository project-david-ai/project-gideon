from __future__ import annotations

from project_gideon.models.approval import ApprovalGrant

from typing import Dict, Generic, List, Tuple, TypeVar

from project_gideon.models import (
    ApprovalRequest,
    CandidateProfile,
    Job,
    JobApplication,
)

ModelT = TypeVar("ModelT")


class _MemoryRepository(Generic[ModelT]):
    """
    Tenant-isolated in-memory repository used for domain and service tests.
    """

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], ModelT] = {}

    async def _save(
        self,
        tenant_id: str,
        resource_id: str,
        value: ModelT,
    ) -> ModelT:
        self._records[(tenant_id, resource_id)] = value
        return value

    async def _get(
        self,
        tenant_id: str,
        resource_id: str,
    ) -> ModelT:
        key = (tenant_id, resource_id)

        if key not in self._records:
            raise KeyError(
                f"Resource not found: tenant={tenant_id!r}, "
                f"id={resource_id!r}"
            )

        return self._records[key]

    async def _list(
        self,
        tenant_id: str,
    ) -> List[ModelT]:
        return [
            value
            for (record_tenant_id, _), value in self._records.items()
            if record_tenant_id == tenant_id
        ]


class InMemoryCandidateRepository(
    _MemoryRepository[CandidateProfile]
):
    async def save(
        self,
        candidate: CandidateProfile,
    ) -> CandidateProfile:
        return await self._save(
            candidate.tenant_id,
            candidate.id,
            candidate,
        )

    async def get(
        self,
        candidate_id: str,
        tenant_id: str,
    ) -> CandidateProfile:
        return await self._get(
            tenant_id,
            candidate_id,
        )

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[CandidateProfile]:
        return await self._list(tenant_id)


class InMemoryJobRepository(
    _MemoryRepository[Job]
):
    async def save(
        self,
        job: Job,
    ) -> Job:
        return await self._save(
            job.tenant_id,
            job.id,
            job,
        )

    async def get(
        self,
        job_id: str,
        tenant_id: str,
    ) -> Job:
        return await self._get(
            tenant_id,
            job_id,
        )

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[Job]:
        return await self._list(tenant_id)


class InMemoryApplicationRepository(
    _MemoryRepository[JobApplication]
):
    async def save(
        self,
        application: JobApplication,
    ) -> JobApplication:
        return await self._save(
            application.tenant_id,
            application.id,
            application,
        )

    async def get(
        self,
        application_id: str,
        tenant_id: str,
    ) -> JobApplication:
        return await self._get(
            tenant_id,
            application_id,
        )

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[JobApplication]:
        return await self._list(tenant_id)


class InMemoryApprovalRepository(
    _MemoryRepository[ApprovalRequest]
):
    async def save(
        self,
        approval: ApprovalRequest,
    ) -> ApprovalRequest:
        return await self._save(
            approval.tenant_id,
            approval.id,
            approval,
        )

    async def get(
        self,
        approval_id: str,
        tenant_id: str,
    ) -> ApprovalRequest:
        return await self._get(
            tenant_id,
            approval_id,
        )

    async def save_grant(
        self,
        grant: ApprovalGrant,
    ) -> ApprovalGrant:
        store = getattr(
            self,
            "_approval_grants",
            None,
        )

        if store is None:
            store = {}
            self._approval_grants = store

        store[
            (
                grant.tenant_id,
                grant.id,
            )
        ] = grant

        return grant

    async def get_grant(
        self,
        grant_id: str,
        tenant_id: str,
    ) -> ApprovalGrant:
        store = getattr(
            self,
            "_approval_grants",
            None,
        )

        key = (
            tenant_id,
            grant_id,
        )

        if (
            store is None
            or key not in store
        ):
            raise KeyError(
                f"Approval grant not found: {grant_id}"
            )

        return store[key]
    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[ApprovalRequest]:
        return await self._list(tenant_id)