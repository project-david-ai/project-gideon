
from __future__ import annotations

from project_gideon.integrations.jobs.greenhouse import (
    GREENHOUSE_SOURCE,
    GreenhouseJobAcquisitionPort,
)
from project_gideon.models.ats_discovery import (
    ATSProvider,
    ATSRegistration,
)
from project_gideon.models.delegation import (
    JobsDelegationRequest,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)


class GreenhouseRegistrationAcquisitionAdapter:
    """
    Translate a verified Greenhouse ATS registration into the existing
    GreenhouseJobAcquisitionPort request shape.

    No discovery, persistence, or duplicate authority lives here.
    """

    def __init__(
        self,
        acquisition: GreenhouseJobAcquisitionPort,
    ) -> None:
        self._acquisition = acquisition

    @property
    def provider(
        self,
    ) -> ATSProvider:
        return ATSProvider.GREENHOUSE

    def _request(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None,
    ) -> JobsDelegationRequest:
        if (
            registration.provider
            != ATSProvider.GREENHOUSE
        ):
            raise ValueError(
                "Greenhouse registration adapter received "
                f"provider={registration.provider.value!r}."
            )

        parameters: dict[
            str,
            object,
        ] = {
            "boards": [
                {
                    "token": registration.identifier,
                    "company": registration.company_name,
                }
            ]
        }

        if max_jobs is not None:
            parameters[
                "max_jobs_per_board"
            ] = max_jobs

        return JobsDelegationRequest(
            tenant_id=request.tenant_id,
            action=request.action,
            query=request.query,
            source=GREENHOUSE_SOURCE,
            parameters=parameters,
            requested_at=request.requested_at,
        )

    def discover(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        return self._acquisition.discover(
            self._request(
                registration=registration,
                request=request,
                max_jobs=max_jobs,
            )
        )

    def ingest(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        return self._acquisition.ingest(
            self._request(
                registration=registration,
                request=request,
                max_jobs=max_jobs,
            )
        )

    def refresh(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        return self._acquisition.refresh(
            self._request(
                registration=registration,
                request=request,
                max_jobs=max_jobs,
            )
        )
