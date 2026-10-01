
from __future__ import annotations

from collections.abc import Sequence

from pydantic import (
    BaseModel,
    Field,
)

from project_gideon.models.ats_discovery import (
    ATSDiscoveryStatus,
    ATSProvider,
    EmployerTarget,
)
from project_gideon.models.delegation import (
    JobsDelegationRequest,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)
from project_gideon.ports.ats_acquisition import (
    ATSRegistrationAcquisitionPort,
)
from project_gideon.services.ats_discovery import (
    ATSDiscoveryService,
)


EMPLOYER_ATS_SOURCE = "employer_ats"


class EmployerATSAcquisitionParameters(
    BaseModel,
):
    """
    Provider-neutral employer discovery parameters.

    The caller supplies employer identity, never an ATS board token.
    """

    employers: list[
        EmployerTarget
    ] = Field(
        min_length=1
    )

    max_jobs_per_employer: int | None = Field(
        default=None,
        ge=1,
    )


class ATSRegistrationJobAcquisitionRouter:
    """
    Resolve employer ATS registrations and route them to provider adapters.

    This router knows ATS providers only as enum identities. It contains no
    provider-specific request construction and owns no canonical persistence.
    """

    def __init__(
        self,
        *,
        discovery: ATSDiscoveryService,
        providers: Sequence[
            ATSRegistrationAcquisitionPort
        ],
    ) -> None:
        self._discovery = discovery

        self._providers = {
            provider.provider: provider
            for provider in providers
        }

        if (
            len(self._providers)
            != len(providers)
        ):
            raise ValueError(
                "Duplicate ATS provider acquisition adapters."
            )

    def _load_parameters(
        self,
        request: JobsDelegationRequest,
    ) -> EmployerATSAcquisitionParameters:
        if (
            request.source is not None
            and request.source.lower()
            != EMPLOYER_ATS_SOURCE
        ):
            raise ValueError(
                "ATS acquisition router cannot service "
                f"source={request.source!r}."
            )

        payload = dict(
            request.parameters
        )

        if request.employers:
            if "employers" in payload:
                raise ValueError(
                    "Employer targets were supplied through both "
                    "JobsDelegationRequest.employers and parameters."
                )

            payload["employers"] = [
                employer.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                for employer in request.employers
            ]

        if request.max_jobs_per_employer is not None:
            if "max_jobs_per_employer" in payload:
                raise ValueError(
                    "max_jobs_per_employer was supplied through both "
                    "the typed request field and parameters."
                )

            payload[
                "max_jobs_per_employer"
            ] = request.max_jobs_per_employer

        return (
            EmployerATSAcquisitionParameters
            .model_validate(
                payload
            )
        )

    def _resolve_provider(
        self,
        target: EmployerTarget,
    ) -> tuple[
        ATSRegistrationAcquisitionPort,
        object,
    ]:
        result = self._discovery.discover(
            target
        )

        if (
            result.status
            != ATSDiscoveryStatus.FOUND
            or result.registration is None
        ):
            raise ValueError(
                "No verified ATS registration found for "
                f"employer={target.company_name!r}."
            )

        registration = result.registration

        provider = self._providers.get(
            registration.provider
        )

        if provider is None:
            raise ValueError(
                "No acquisition adapter registered for "
                f"ATS provider={registration.provider.value!r}."
            )

        return (
            provider,
            registration,
        )

    def _acquire(
        self,
        *,
        request: JobsDelegationRequest,
        method: str,
    ) -> list[JobIngestionCandidate]:
        parameters = self._load_parameters(
            request
        )

        candidates: list[
            JobIngestionCandidate
        ] = []

        for target in parameters.employers:
            provider, registration = (
                self._resolve_provider(
                    target
                )
            )

            operation = getattr(
                provider,
                method,
            )

            candidates.extend(
                operation(
                    registration=registration,
                    request=request,
                    max_jobs=(
                        parameters
                        .max_jobs_per_employer
                    ),
                )
            )

        return candidates

    def discover(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._acquire(
            request=request,
            method="discover",
        )

    def ingest(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._acquire(
            request=request,
            method="ingest",
        )

    def refresh(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._acquire(
            request=request,
            method="refresh",
        )
