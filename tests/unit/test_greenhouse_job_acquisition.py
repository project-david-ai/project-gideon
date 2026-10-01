
import pytest
from pydantic import ValidationError

from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
    GreenhouseJobsResponse,
    greenhouse_html_to_text,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)


def make_request(
    **updates,
):
    values = {
        "tenant_id": "tenant-1",
        "action": JobsDelegationAction.DISCOVER,
        "source": "greenhouse",
        "parameters": {
            "boards": [
                {
                    "token": "acme",
                    "company": "Acme",
                }
            ]
        },
    }

    values.update(
        updates
    )

    return JobsDelegationRequest(
        **values
    )


def greenhouse_payload():
    return {
        "jobs": [
            {
                "id": 12345,
                "title": "Senior Network Engineer",
                "absolute_url": (
                    "https://boards.greenhouse.io/"
                    "acme/jobs/12345"
                ),
                "content": (
                    "<h2>About the role</h2>"
                    "<p>Build global networks.</p>"
                ),
                "company_name": "Acme Corporation",
                "requisition_id": "REQ-77",
                "internal_job_id": 9001,
                "location": {
                    "name": "Berlin, Germany",
                },
                "departments": [
                    {
                        "id": 1,
                        "name": "Infrastructure",
                    }
                ],
                "offices": [
                    {
                        "id": 2,
                        "name": "Berlin",
                    }
                ],
                "first_published": "2026-09-28T12:00:00Z",
                "updated_at": "2026-10-01T10:30:00Z",
                "metadata": [
                    {
                        "name": "Employment Type",
                        "value": "Full-time",
                    }
                ],
            }
        ],
        "meta": {
            "total": 1,
        },
    }


def test_html_is_normalised_to_plain_text():
    result = greenhouse_html_to_text(
        "<h1>Hello</h1><p>World &amp; team</p>"
    )

    assert result == "Hello World & team"


def test_public_greenhouse_payload_is_validated_and_normalised():
    calls = []

    def fake_get(
        url,
    ):
        calls.append(
            url
        )

        return greenhouse_payload()

    adapter = GreenhouseJobAcquisitionPort(
        json_get=fake_get
    )

    candidates = adapter.discover(
        make_request()
    )

    assert calls == [
        (
            "https://boards-api.greenhouse.io/"
            "v1/boards/acme/jobs?content=true"
        )
    ]

    assert len(candidates) == 1

    candidate = candidates[0]
    job = candidate.job

    assert job.id == "greenhouse:acme:12345"
    assert job.tenant_id == "tenant-1"
    assert job.source == "greenhouse"
    assert job.source_job_id == "12345"
    assert job.company == "Acme Corporation"
    assert job.title == "Senior Network Engineer"
    assert job.location == "Berlin, Germany"

    assert (
        job.description
        == "About the role Build global networks."
    )

    assert candidate.requisition_id == "REQ-77"

    assert (
        job.meta_data["source_type"]
        == "employer_ats"
    )

    assert (
        job.meta_data["board_token"]
        == "acme"
    )

    assert job.meta_data["departments"] == [
        "Infrastructure"
    ]

    assert job.meta_data["offices"] == [
        "Berlin"
    ]


def test_board_company_is_fallback_when_payload_has_no_company():
    payload = greenhouse_payload()

    payload["jobs"][0].pop(
        "company_name"
    )

    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: payload
    )

    candidate = adapter.discover(
        make_request()
    )[0]

    assert candidate.job.company == "Acme"


def test_board_token_is_last_resort_company_identity():
    payload = greenhouse_payload()

    payload["jobs"][0].pop(
        "company_name"
    )

    request = make_request(
        parameters={
            "boards": [
                {
                    "token": "acme",
                }
            ]
        }
    )

    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: payload
    )

    candidate = adapter.discover(
        request
    )[0]

    assert candidate.job.company == "acme"


def test_multiple_boards_are_supported():
    calls = []

    def fake_get(
        url,
    ):
        calls.append(
            url
        )

        payload = greenhouse_payload()

        payload["jobs"][0]["id"] = len(
            calls
        )

        payload["jobs"][0]["absolute_url"] = (
            f"https://example.com/{len(calls)}"
        )

        return payload

    request = make_request(
        parameters={
            "boards": [
                {
                    "token": "alpha",
                    "company": "Alpha",
                },
                {
                    "token": "beta",
                    "company": "Beta",
                },
            ]
        }
    )

    adapter = GreenhouseJobAcquisitionPort(
        json_get=fake_get
    )

    candidates = adapter.discover(
        request
    )

    assert len(candidates) == 2

    assert calls == [
        (
            "https://boards-api.greenhouse.io/"
            "v1/boards/alpha/jobs?content=true"
        ),
        (
            "https://boards-api.greenhouse.io/"
            "v1/boards/beta/jobs?content=true"
        ),
    ]


def test_max_jobs_per_board_is_enforced():
    payload = greenhouse_payload()

    payload["jobs"] = (
        payload["jobs"]
        * 5
    )

    request = make_request(
        parameters={
            "boards": [
                {
                    "token": "acme",
                }
            ],
            "max_jobs_per_board": 2,
        }
    )

    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: payload
    )

    assert len(
        adapter.discover(
            request
        )
    ) == 2


def test_wrong_source_is_rejected():
    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: greenhouse_payload()
    )

    with pytest.raises(
        ValueError,
        match="cannot service",
    ):
        adapter.discover(
            make_request(
                source="linkedin"
            )
        )


def test_missing_boards_fails_source_specific_validation():
    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: greenhouse_payload()
    )

    with pytest.raises(
        ValidationError,
    ):
        adapter.discover(
            make_request(
                parameters={}
            )
        )


def test_discover_ingest_and_refresh_use_same_structured_source():
    calls = []

    def fake_get(
        url,
    ):
        calls.append(
            url
        )

        return {
            "jobs": [],
        }

    adapter = GreenhouseJobAcquisitionPort(
        json_get=fake_get
    )

    request = make_request()

    assert adapter.discover(
        request
    ) == []

    assert adapter.ingest(
        request
    ) == []

    assert adapter.refresh(
        request
    ) == []

    assert len(calls) == 3


def test_response_tolerates_unknown_greenhouse_fields():
    payload = greenhouse_payload()

    payload["future_greenhouse_field"] = {
        "anything": True,
    }

    payload["jobs"][0]["future_job_field"] = "value"

    result = GreenhouseJobsResponse.model_validate(
        payload
    )

    assert len(result.jobs) == 1


def test_null_greenhouse_metadata_is_accepted_and_normalised():
    payload = greenhouse_payload()

    payload["jobs"][0]["metadata"] = None

    adapter = GreenhouseJobAcquisitionPort(
        json_get=lambda url: payload
    )

    candidate = adapter.discover(
        make_request()
    )[0]

    assert candidate.job.meta_data["metadata"] == []
