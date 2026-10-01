
from project_gideon.integrations.jobs.ats_routing import (
    ATSRegistrationJobAcquisitionRouter,
)
from project_gideon.integrations.jobs.delegation import (
    GideonJobsDelegationPort,
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
from project_gideon.models.job import Job
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
    JobIngestionResult,
)
from project_gideon.models.presentation import (
    PresentationState,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
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
                identifier="secret-board-token",
                careers_url=(
                    "https://example.test/careers"
                ),
                provider_url=(
                    "https://job-boards.greenhouse.io/"
                    "secret-board-token"
                ),
                api_url=(
                    "https://boards-api.greenhouse.io/"
                    "v1/boards/secret-board-token/jobs"
                ),
            ),
        )


class Provider:
    provider = ATSProvider.GREENHOUSE

    def discover(
        self,
        *,
        registration,
        request,
        max_jobs=None,
    ):
        return [
            JobIngestionCandidate(
                job=Job(
                    id="source-job",
                    tenant_id=request.tenant_id,
                    source="greenhouse",
                    source_job_id="123",
                    source_url=(
                        "https://example.test/job/123"
                    ),
                    application_url=(
                        "https://example.test/job/123"
                    ),
                    title="Network Engineer",
                    company=registration.company_name,
                    description="Role",
                    requirements=[],
                    meta_data={},
                ),
                requisition_id=None,
            )
        ]

    ingest = discover
    refresh = discover


class Ingestion:
    def ingest(
        self,
        candidate,
    ):
        return JobIngestionResult(
            job=candidate.job,
            match_type="distinct",
            created=True,
            provenance={},
        )


def test_jobs_feedback_is_semantic_and_domain_focused():
    events = []

    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            Provider(),
        ],
    )

    port = GideonJobsDelegationPort(
        acquisition=router,
        ingestion=Ingestion(),
    )

    service = JobsDelegationService(
        port
    )

    service.bind_presentation(
        presentation_sink=events.append,
    )

    result = service.delegate(
        JobsDelegationRequest(
            tenant_id="tenant-1",
            action=JobsDelegationAction.DISCOVER,
            employers=[
                {
                    "company_name": "Stripe",
                    "careers_url": (
                        "https://stripe.com/careers"
                    ),
                }
            ],
            max_jobs_per_employer=1,
        )
    )

    assert result.ingested_count == 1

    titles = [
        event.title
        for event in events
    ]

    assert (
        "Searching current opportunities"
        in titles
    )

    assert any(
        "Identifying Stripe" in title
        for title in titles
    )

    assert any(
        "Verified recruiting source" in title
        for title in titles
    )

    assert any(
        "Fetching current roles" in title
        for title in titles
    )

    assert any(
        "Found 1 current role" in title
        for title in titles
    )

    assert any(
        "1 new opportunity added" in title
        for title in titles
    )

    assert all(
        event.faction == "jobs"
        for event in events
    )

    assert any(
        event.state
        is PresentationState.SUCCESS
        for event in events
    )


def test_jobs_feedback_does_not_expose_board_token():
    events = []

    router = ATSRegistrationJobAcquisitionRouter(
        discovery=StaticDiscovery(),
        providers=[
            Provider(),
        ],
    )

    port = GideonJobsDelegationPort(
        acquisition=router,
        ingestion=Ingestion(),
    )

    port.bind_presentation(
        presentation_sink=events.append,
    )

    port.delegate_jobs(
        JobsDelegationRequest(
            tenant_id="tenant-1",
            action=JobsDelegationAction.DISCOVER,
            employers=[
                {
                    "company_name": "Stripe",
                    "careers_url": (
                        "https://stripe.com/careers"
                    ),
                }
            ],
        )
    )

    rendered = " ".join(
        (
            event.title
            + " "
            + (
                event.detail
                or ""
            )
        )
        for event in events
    ).lower()

    assert "secret-board-token" not in rendered
    assert "boards-api" not in rendered
