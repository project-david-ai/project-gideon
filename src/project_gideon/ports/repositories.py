from __future__ import annotations

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

    async def list_for_tenant(
        self,
        tenant_id: str,
    ) -> List[ApprovalRequest]:
        ...