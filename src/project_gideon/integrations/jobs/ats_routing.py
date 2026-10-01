
from __future__ import annotations

from collections.abc import Callable, Sequence

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
from project_gideon.models.presentation import (
    GideonPresentationEvent,
    PresentationEventType,
    PresentationState,
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
        self._presentation_sink: (
            Callable[
                [GideonPresentationEvent],
                None,
            ]
            | None
        ) = None

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

    def bind_presentation(
        self,
        *,
        presentation_sink: Callable[
            [GideonPresentationEvent],
            None,
        ]
        | None,
    ) -> None:
        self._presentation_sink = presentation_sink

    def _present(
        self,
        *,
        title: str,
        state: PresentationState = PresentationState.IN_PROGRESS,
        detail: str | None = None,
        source_url: str | None = None,
        meta_data: dict[str, object] | None = None,
    ) -> None:
        if self._presentation_sink is None:
            return

        self._presentation_sink(
            GideonPresentationEvent(
                type=PresentationEventType.ACTIVITY,
                state=state,
                phase="jobs",
                faction="jobs",
                title=title,
                detail=detail,
                source_url=source_url,
                meta_data=dict(
                    meta_data or {}
                ),
            )
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
        self._present(
            title=(
                f"Identifying {target.company_name}'s "
                "recruiting system"
            ),
            detail=(
                "Checking employer-owned recruiting sources."
            ),
        )

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

        self._present(
            title=(
                f"Verified recruiting source for "
                f"{target.company_name}"
            ),
            state=PresentationState.SUCCESS,
            detail=(
                f"Using verified "
                f"{registration.provider.value} "
                "employer data."
            ),
            source_url=(
                str(
                    registration.careers_url
                )
                if registration.careers_url
                else None
            ),
            meta_data={
                "provider": (
                    registration.provider.value
                ),
            },
        )

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

            self._present(
                title=(
                    f"Fetching current roles from "
                    f"{target.company_name}"
                ),
            )

            discovered = operation(
                registration=registration,
                request=request,
                max_jobs=(
                    parameters
                    .max_jobs_per_employer
                ),
            )

            candidates.extend(
                discovered
            )

            self._present(
                title=(
                    f"Found {len(discovered)} "
                    f"current role"
                    + (
                        ""
                        if len(discovered) == 1
                        else "s"
                    )
                    + f" at {target.company_name}"
                ),
                state=PresentationState.SUCCESS,
                meta_data={
                    "count": len(
                        discovered
                    ),
                },
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
