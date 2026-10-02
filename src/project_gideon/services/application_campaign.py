from __future__ import annotations

from uuid import uuid4

from project_gideon.models import (
    ApplicationState,
    JobApplication,
)
from project_gideon.ports import (
    ApplicationRepository,
    CandidateRepository,
    JobRepository,
)
from project_gideon.services.application_lifecycle import (
    ApplicationLifecycleService,
)


class ApplicationCampaignError(ValueError):
    pass


class ApplicationCampaignService:
    """
    Own the durable campaign boundary between canonical jobs and applications.

    Job discovery does not itself create an application campaign. Shortlisting
    establishes one durable JobApplication for a tenant/job/candidate tuple.
    Lifecycle transitions remain owned by ApplicationLifecycleService.
    """

    def __init__(
        self,
        *,
        jobs: JobRepository,
        candidates: CandidateRepository,
        applications: ApplicationRepository,
    ) -> None:
        self._jobs = jobs
        self._candidates = candidates
        self._applications = applications
        self._lifecycle = ApplicationLifecycleService(
            applications
        )

    async def shortlist(
        self,
        *,
        tenant_id: str,
        job_id: str,
        candidate_id: str,
    ) -> JobApplication:
        await self._jobs.get(
            job_id,
            tenant_id,
        )

        await self._candidates.get(
            candidate_id,
            tenant_id,
        )

        existing = [
            application
            for application
            in await self._applications.list_for_tenant(
                tenant_id
            )
            if (
                application.job_id == job_id
                and application.candidate_id == candidate_id
            )
        ]

        if len(existing) > 1:
            raise ApplicationCampaignError(
                "Multiple applications exist for the same "
                "tenant/job/candidate campaign."
            )

        if existing:
            application = existing[0]

            if application.state is ApplicationState.DISCOVERED:
                return await self._lifecycle.transition(
                    application_id=application.id,
                    tenant_id=tenant_id,
                    target=ApplicationState.SHORTLISTED,
                )

            return application

        application = JobApplication(
            id=f"application_{uuid4().hex}",
            tenant_id=tenant_id,
            job_id=job_id,
            candidate_id=candidate_id,
        )

        application = await self._applications.save(
            application
        )

        return await self._lifecycle.transition(
            application_id=application.id,
            tenant_id=tenant_id,
            target=ApplicationState.SHORTLISTED,
        )

    async def start_preparation(
        self,
        *,
        application_id: str,
        tenant_id: str,
    ) -> JobApplication:
        application = await self._applications.get(
            application_id,
            tenant_id,
        )

        if application.state is ApplicationState.PREPARING:
            return application

        if application.state is not ApplicationState.SHORTLISTED:
            raise ApplicationCampaignError(
                "Application cannot start preparation from "
                f"state={application.state.value}."
            )

        return await self._lifecycle.transition(
            application_id=application.id,
            tenant_id=tenant_id,
            target=ApplicationState.PREPARING,
        )
