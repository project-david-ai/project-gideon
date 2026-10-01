
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    model_validator,
)


def utc_now() -> datetime:
    return datetime.now(
        timezone.utc
    )


class ATSProvider(
    str,
    Enum,
):
    GREENHOUSE = "greenhouse"


class ATSDiscoveryStatus(
    str,
    Enum,
):
    FOUND = "found"
    NOT_FOUND = "not_found"


class ATSDiscoveryEvidenceType(
    str,
    Enum,
):
    CAREERS_PAGE = "careers_page"
    PROVIDER_LINK = "provider_link"
    PROVIDER_API = "provider_api"


class EmployerTarget(BaseModel):
    """
    Employer identity supplied to the ATS discovery layer.

    careers_url is preferred when already known. domain allows bounded,
    deterministic career-page probing when no explicit URL is available.
    """

    company_name: str = Field(
        min_length=1
    )

    domain: str | None = None
    careers_url: HttpUrl | None = None

    @model_validator(
        mode="after"
    )
    def require_discovery_locator(
        self,
    ) -> "EmployerTarget":
        if (
            not self.domain
            and self.careers_url is None
        ):
            raise ValueError(
                "EmployerTarget requires domain or careers_url."
            )

        return self


class ATSDiscoveryEvidence(BaseModel):
    type: ATSDiscoveryEvidenceType
    url: HttpUrl
    detail: str | None = None


class ATSRegistration(BaseModel):
    """
    Verified provider registration discovered for one employer.
    """

    company_name: str
    provider: ATSProvider

    identifier: str

    careers_url: HttpUrl | None = None
    provider_url: HttpUrl
    api_url: HttpUrl

    evidence: list[
        ATSDiscoveryEvidence
    ] = Field(
        default_factory=list
    )

    verified_at: datetime = Field(
        default_factory=utc_now
    )


class ATSDiscoveryResult(BaseModel):
    status: ATSDiscoveryStatus

    target: EmployerTarget

    registration: ATSRegistration | None = None

    checked_urls: list[HttpUrl] = Field(
        default_factory=list
    )

    @model_validator(
        mode="after"
    )
    def validate_status_shape(
        self,
    ) -> "ATSDiscoveryResult":
        if (
            self.status
            == ATSDiscoveryStatus.FOUND
            and self.registration is None
        ):
            raise ValueError(
                "FOUND discovery result requires registration."
            )

        if (
            self.status
            == ATSDiscoveryStatus.NOT_FOUND
            and self.registration is not None
        ):
            raise ValueError(
                "NOT_FOUND discovery result cannot include registration."
            )

        return self
