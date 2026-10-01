
from project_gideon.integrations.jobs.greenhouse_discovery import (
    ATSPageResponse,
    GreenhouseATSDetector,
)
from project_gideon.models.ats_discovery import (
    ATSProvider,
    EmployerTarget,
)


def valid_jobs_payload():
    return {
        "jobs": [
            {
                "id": 123,
                "title": "Network Engineer",
                "absolute_url": (
                    "https://job-boards.greenhouse.io/"
                    "acme/jobs/123"
                ),
                "location": {
                    "name": "Berlin",
                },
                "metadata": None,
            }
        ]
    }


def test_detects_greenhouse_from_provider_link_in_careers_html():
    page_calls = []
    api_calls = []

    def page_get(
        url,
    ):
        page_calls.append(
            url
        )

        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                '<a href="https://job-boards.greenhouse.io/'
                'acme">Open roles</a>'
            ),
        )

    def json_get(
        url,
    ):
        api_calls.append(
            url
        )

        return valid_jobs_payload()

    detector = GreenhouseATSDetector(
        page_get=page_get,
        json_get=json_get,
    )

    target = EmployerTarget(
        company_name="Acme",
        careers_url=(
            "https://www.acme.example/careers"
        ),
    )

    registration = detector.detect(
        target
    )

    assert registration is not None

    assert (
        registration.provider
        == ATSProvider.GREENHOUSE
    )

    assert registration.identifier == "acme"

    assert page_calls == [
        "https://www.acme.example/careers"
    ]

    assert api_calls == [
        (
            "https://boards-api.greenhouse.io/"
            "v1/boards/acme/jobs?content=false"
        )
    ]

    assert len(
        registration.evidence
    ) == 3


def test_detects_greenhouse_from_redirected_provider_url():
    detector = GreenhouseATSDetector(
        page_get=lambda url: ATSPageResponse(
            requested_url=url,
            final_url=(
                "https://job-boards.greenhouse.io/acme"
            ),
            status_code=200,
            text="",
        ),
        json_get=lambda url: valid_jobs_payload(),
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Acme",
            careers_url=(
                "https://www.acme.example/jobs"
            ),
        )
    )

    assert registration is not None
    assert registration.identifier == "acme"


def test_domain_only_discovery_uses_bounded_career_paths():
    calls = []

    def page_get(
        url,
    ):
        calls.append(
            url
        )

        if url.endswith(
            "/careers"
        ):
            return ATSPageResponse(
                requested_url=url,
                final_url=url,
                status_code=404,
                text="",
            )

        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                "https://boards.greenhouse.io/acme"
            ),
        )

    detector = GreenhouseATSDetector(
        page_get=page_get,
        json_get=lambda url: valid_jobs_payload(),
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Acme",
            domain="acme.example",
        )
    )

    assert registration is not None

    assert calls == [
        "https://acme.example/careers",
        "https://acme.example/jobs",
    ]


def test_provider_evidence_without_valid_api_is_rejected():
    detector = GreenhouseATSDetector(
        page_get=lambda url: ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                "https://boards.greenhouse.io/acme"
            ),
        ),
        json_get=lambda url: {
            "not_jobs": [],
        },
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Acme",
            careers_url=(
                "https://acme.example/careers"
            ),
        )
    )

    assert registration is None


def test_no_provider_evidence_returns_none_without_api_guessing():
    api_calls = []

    detector = GreenhouseATSDetector(
        page_get=lambda url: ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text="<html>No ATS provider here.</html>",
        ),
        json_get=lambda url: (
            api_calls.append(url)
            or valid_jobs_payload()
        ),
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Acme",
            careers_url=(
                "https://acme.example/careers"
            ),
        )
    )

    assert registration is None
    assert api_calls == []


def test_unrelated_greenhouse_token_is_not_derived_from_company_name():
    api_calls = []

    detector = GreenhouseATSDetector(
        page_get=lambda url: ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text="<html>Careers</html>",
        ),
        json_get=lambda url: (
            api_calls.append(url)
            or valid_jobs_payload()
        ),
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Definitely Acme",
            domain="acme.example",
        )
    )

    assert registration is None
    assert api_calls == []
