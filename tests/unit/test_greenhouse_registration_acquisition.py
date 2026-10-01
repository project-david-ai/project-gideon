
from project_gideon.integrations.jobs.greenhouse_registration_acquisition import (
    GreenhouseRegistrationAcquisitionAdapter,
)
from project_gideon.models.ats_discovery import (
    ATSProvider,
    ATSRegistration,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)


class CaptureAcquisition:
    def __init__(
        self,
    ):
        self.request = None

    def discover(
        self,
        request,
    ):
        self.request = request
        return []

    def ingest(
        self,
        request,
    ):
        self.request = request
        return []

    def refresh(
        self,
        request,
    ):
        self.request = request
        return []


def test_greenhouse_registration_maps_to_existing_request_contract():
    capture = CaptureAcquisition()

    adapter = GreenhouseRegistrationAcquisitionAdapter(
        capture
    )

    registration = ATSRegistration(
        company_name="Stripe",
        provider=ATSProvider.GREENHOUSE,
        identifier="stripe",
        provider_url=(
            "https://job-boards.greenhouse.io/stripe"
        ),
        api_url=(
            "https://boards-api.greenhouse.io/"
            "v1/boards/stripe/jobs?content=false"
        ),
    )

    original = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="network engineer",
        source="employer_ats",
        parameters={},
    )

    result = adapter.discover(
        registration=registration,
        request=original,
        max_jobs=5,
    )

    assert result == []

    assert capture.request is not None

    assert capture.request.tenant_id == "tenant-1"
    assert capture.request.query == "network engineer"
    assert capture.request.source == "greenhouse"

    assert capture.request.parameters == {
        "boards": [
            {
                "token": "stripe",
                "company": "Stripe",
            }
        ],
        "max_jobs_per_board": 5,
    }
