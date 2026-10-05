from __future__ import annotations

from project_gideon.models.approval import ApprovalGrant

from typing import List, Protocol

from project_gideon.models import (
    ApprovalRequest,
    CandidateProfile,
    Job,
    JobApplication,
)


class CandidateRepository(Protocol):
    async def save(
        self,
        candidate: CandidateProfile,
    ) -> CandidateProfile:
        ...

    async def get(
        self,
        candidate_id: str,
        tenant_id: str,
    ) -> CandidateProfile:
        ...

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[CandidateProfile]:
        ...


class JobRepository(Protocol):
    async def save(
        self,
        job: Job,
    ) -> Job:
        ...

    async def get(
        self,
        job_id: str,
        tenant_id: str,
    ) -> Job:
        ...

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[Job]:
        ...


class ApplicationRepository(Protocol):
    async def save(
        self,
        application: JobApplication,
    ) -> JobApplication:
        ...

    async def get(
        self,
        application_id: str,
        tenant_id: str,
    ) -> JobApplication:
        ...

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[JobApplication]:
        ...


class ApprovalRepository(Protocol):
    async def save(
        self,
        approval: ApprovalRequest,
    ) -> ApprovalRequest:
        ...

    async def get(
        self,
        approval_id: str,
        tenant_id: str,
    ) -> ApprovalRequest:
        ...

    async def save_grant(
        self,
        grant: ApprovalGrant,
    ) -> ApprovalGrant:
        ...

    async def get_grant(
        self,
        grant_id: str,
        tenant_id: str,
    ) -> ApprovalGrant:
        ...
    async def claim_grant(
        self,
        grant: ApprovalGrant,
    ) -> ApprovalGrant | None:
        """
        Atomically persist the supplied consumed representation
        only when the currently stored grant is still unconsumed.

        Return None when another caller has already claimed it.
        """
        ...
    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[ApprovalRequest]:
        ...
