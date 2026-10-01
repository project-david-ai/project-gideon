
from project_gideon.integrations.jobs.ats_routing import (
    ATSRegistrationJobAcquisitionRouter,
)
from project_gideon.models.ats_discovery import (
    ATSDiscoveryResult,
    ATSDiscoveryStatus,
    ATSProvider,
    ATSRegistration,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)


class StaticDiscovery:
    def __init__(
        self,
    ):
        self.targets = []

    def discover(
        self,
        target,
    ):
        self.targets.append(
            target
        )

        return ATSDiscoveryResult(
            status=ATSDiscoveryStatus.FOUND,
            target=target,
            registration=ATSRegistration(
                company_name=target.company_name,
                provider=ATSProvider.GREENHOUSE,
                identifier="stripe",
                provider_url=(
                    "https://job-boards.greenhouse.io/stripe"
                ),
                api_url=(
                    "https://boards-api.greenhouse.io/"
                    "v1/boards/stripe/jobs?content=false"
                ),
            ),
        )


class CaptureProvider:
    provider = ATSProvider.GREENHOUSE

    def __init__(
        self,
    ):
        self.calls = []

    def discover(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        self.calls.append(
            (
                registration.identifier,
                request.source,
                max_jobs,
            )
        )

        return []

    def ingest(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return self.discover(
            registration=registration,
            request=request,
            max_jobs=max_jobs,
        )

    def refresh(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return self.discover(
            registration=registration,
            request=request,
            max_jobs=max_jobs,
        )


def test_router_consumes_typed_employer_target_without_source_hint():
    discovery = StaticDiscovery()
    provider = CaptureProvider()

    router = ATSRegistrationJobAcquisitionRouter(
        discovery=discovery,
        providers=[
            provider,
        ],
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="jobs at Stripe",
        employers=[
            {
                "company_name": "Stripe",
                "careers_url": (
                    "https://stripe.com/careers/search"
                ),
            }
        ],
        max_jobs_per_employer=3,
    )

    result = router.discover(
        request
    )

    assert result == []

    assert len(
        discovery.targets
    ) == 1

    assert (
        discovery.targets[0].company_name
        == "Stripe"
    )

    assert provider.calls == [
        (
            "stripe",
            None,
            3,
        )
    ]


def test_router_rejects_duplicate_employer_sources():
    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            CaptureProvider(),
        ],
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        employers=[
            {
                "company_name": "Stripe",
                "careers_url": (
                    "https://stripe.com/careers/search"
                ),
            }
        ],
        parameters={
            "employers": [
                {
                    "company_name": "Other",
                    "careers_url": (
                        "https://other.example/careers"
                    ),
                }
            ]
        },
    )

    try:
        router.discover(
            request
        )
    except ValueError as exc:
        assert (
            "supplied through both"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected duplicate employer source failure."
        )


def test_router_rejects_duplicate_max_jobs_sources():
    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            CaptureProvider(),
        ],
    )

    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        employers=[
            {
                "company_name": "Stripe",
                "careers_url": (
                    "https://stripe.com/careers/search"
                ),
            }
        ],
        max_jobs_per_employer=3,
        parameters={
            "max_jobs_per_employer": 5,
        },
    )

    try:
        router.discover(
            request
        )
    except ValueError as exc:
        assert (
            "supplied through both"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected duplicate max-jobs source failure."
        )
