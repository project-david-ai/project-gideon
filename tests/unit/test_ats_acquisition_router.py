
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
from project_gideon.models.job import (
    Job,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)


class StaticDiscovery:
    def discover(
        self,
        target,
    ):
        return ATSDiscoveryResult(
            status=ATSDiscoveryStatus.FOUND,
            target=target,
            registration=ATSRegistration(
                company_name=target.company_name,
                provider=ATSProvider.GREENHOUSE,
                identifier="verified-board",
                provider_url=(
                    "https://job-boards.greenhouse.io/"
                    "verified-board"
                ),
                api_url=(
                    "https://boards-api.greenhouse.io/"
                    "v1/boards/verified-board/jobs"
                    "?content=false"
                ),
            ),
        )


class MissingDiscovery:
    def discover(
        self,
        target,
    ):
        return ATSDiscoveryResult(
            status=ATSDiscoveryStatus.NOT_FOUND,
            target=target,
        )


class Provider:
    provider = ATSProvider.GREENHOUSE

    def __init__(
        self,
    ):
        self.calls = []

    def _candidate(
        self,
        registration,
        request,
        max_jobs,
        method,
    ):
        self.calls.append(
            (
                method,
                registration.identifier,
                request.source,
                max_jobs,
            )
        )

        return [
            JobIngestionCandidate(
                job=Job(
                    id="greenhouse:verified-board:123",
                    tenant_id=request.tenant_id,
                    source="greenhouse",
                    source_job_id="123",
                    source_url=(
                        "https://example.test/jobs/123"
                    ),
                    application_url=(
                        "https://example.test/jobs/123"
                    ),
                    title="Network Engineer",
                    company=registration.company_name,
                    description="Synthetic test role.",
                    requirements=[],
                    meta_data={},
                ),
                requisition_id=None,
            )
        ]

    def discover(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return self._candidate(
            registration,
            request,
            max_jobs,
            "discover",
        )

    def ingest(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return self._candidate(
            registration,
            request,
            max_jobs,
            "ingest",
        )

    def refresh(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return self._candidate(
            registration,
            request,
            max_jobs,
            "refresh",
        )


def request():
    return JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        source="employer_ats",
        parameters={
            "employers": [
                {
                    "company_name": "Acme",
                    "careers_url": (
                        "https://acme.example/careers"
                    ),
                }
            ],
            "max_jobs_per_employer": 3,
        },
    )


def test_router_discovers_registration_then_routes_provider():
    provider = Provider()

    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            provider,
        ],
    )

    candidates = router.discover(
        request()
    )

    assert len(candidates) == 1

    assert provider.calls == [
        (
            "discover",
            "verified-board",
            "employer_ats",
            3,
        )
    ]


def test_router_fails_when_employer_has_no_verified_registration():
    router = ATSRegistrationJobAcquisitionRouter(
        discovery=MissingDiscovery(),
        providers=[
            Provider(),
        ],
    )

    try:
        router.discover(
            request()
        )
    except ValueError as exc:
        assert (
            "No verified ATS registration"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected unresolved ATS registration failure."
        )


def test_router_rejects_non_employer_ats_source():
    provider = Provider()

    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            provider,
        ],
    )

    bad = request().model_copy(
        update={
            "source": "greenhouse",
        }
    )

    try:
        router.discover(
            bad
        )
    except ValueError as exc:
        assert (
            "cannot service"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected source boundary failure."
        )


def test_router_rejects_duplicate_provider_adapters():
    try:
        ATSRegistrationJobAcquisitionRouter(
            discovery=StaticDiscovery(),
            providers=[
                Provider(),
                Provider(),
            ],
        )
    except ValueError as exc:
        assert (
            "Duplicate ATS provider"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected duplicate provider failure."
        )
