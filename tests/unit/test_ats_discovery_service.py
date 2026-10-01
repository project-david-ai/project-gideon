
from project_gideon.models.ats_discovery import (
    ATSDiscoveryStatus,
    ATSProvider,
    ATSRegistration,
    EmployerTarget,
)
from project_gideon.services.ats_discovery import (
    ATSDiscoveryService,
)


class NullDetector:
    def detect(
        self,
        target,
    ):
        return None


class StaticDetector:
    def detect(
        self,
        target,
    ):
        return ATSRegistration(
            company_name=target.company_name,
            provider=ATSProvider.GREENHOUSE,
            identifier="acme",
            provider_url=(
                "https://job-boards.greenhouse.io/acme"
            ),
            api_url=(
                "https://boards-api.greenhouse.io/"
                "v1/boards/acme/jobs?content=false"
            ),
        )


def test_discovery_service_returns_first_verified_registration():
    service = ATSDiscoveryService(
        [
            NullDetector(),
            StaticDetector(),
        ]
    )

    target = EmployerTarget(
        company_name="Acme",
        domain="acme.example",
    )

    result = service.discover(
        target
    )

    assert (
        result.status
        == ATSDiscoveryStatus.FOUND
    )

    assert result.registration is not None

    assert (
        result.registration.provider
        == ATSProvider.GREENHOUSE
    )

    assert (
        result.registration.identifier
        == "acme"
    )


def test_discovery_service_returns_typed_not_found():
    service = ATSDiscoveryService(
        [
            NullDetector(),
        ]
    )

    target = EmployerTarget(
        company_name="Acme",
        domain="acme.example",
    )

    result = service.discover(
        target
    )

    assert (
        result.status
        == ATSDiscoveryStatus.NOT_FOUND
    )

    assert result.registration is None
