
from __future__ import annotations

from typing import Protocol

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


class ATSRegistrationAcquisitionPort(
    Protocol,
):
    """
    Provider-specific acquisition adapter consuming a verified ATS registration.

    This boundary translates a provider-neutral ATSRegistration into the
    provider's existing JobAcquisitionPort contract. It owns no persistence.
    """

    @property
    def provider(
        self,
    ) -> ATSProvider:
        ...

    def discover(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        ...

    def ingest(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        ...

    def refresh(
        self,
        *,
        registration: ATSRegistration,
        request: JobsDelegationRequest,
        max_jobs: int | None = None,
    ) -> list[JobIngestionCandidate]:
        ...
