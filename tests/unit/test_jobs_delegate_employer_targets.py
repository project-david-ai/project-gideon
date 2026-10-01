
from project_gideon.integrations.project_david.consumer_tools.jobs import (
    build_jobs_delegate_tool,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)


def test_jobs_request_accepts_native_employer_targets():
    request = JobsDelegationRequest(
        tenant_id="tenant-1",
        action=JobsDelegationAction.DISCOVER,
        query="network engineer jobs at Stripe",
        employers=[
            {
                "company_name": "Stripe",
                "careers_url": (
                    "https://stripe.com/careers/search"
                ),
            }
        ],
        max_jobs_per_employer=5,
    )

    assert request.source is None
    assert request.parameters == {}

    assert len(
        request.employers
    ) == 1

    assert (
        request.employers[0].company_name
        == "Stripe"
    )

    assert (
        request.max_jobs_per_employer
        == 5
    )


def test_jobs_tool_schema_exposes_native_employer_fields():
    tool = build_jobs_delegate_tool()

    properties = (
        tool[
            "function"
        ][
            "parameters"
        ][
            "properties"
        ]
    )

    assert "employers" in properties

    assert (
        "max_jobs_per_employer"
        in properties
    )


def test_jobs_tool_keeps_legacy_parameters_compatibility():
    tool = build_jobs_delegate_tool()

    properties = (
        tool[
            "function"
        ][
            "parameters"
        ][
            "properties"
        ]
    )

    assert "parameters" in properties


def test_jobs_tool_tells_supervisor_not_to_guess_ats_identity():
    tool = build_jobs_delegate_tool()

    description = (
        tool[
            "function"
        ][
            "description"
        ].lower()
    )

    assert "employer" in description

    assert (
        "should not be guessed"
        in description
    )
