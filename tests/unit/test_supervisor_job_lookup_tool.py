from __future__ import annotations

import json

from project_gideon.integrations.project_david.consumer_tools.job_lookup import (
    JOB_LOOKUP_TOOL_NAME,
    build_job_lookup_tool,
    create_job_lookup_handler,
)
from project_gideon.models.job import Job


TENANT_ID = "tenant-1"
JOB_ID = "job-1"


class FakeCanonicalJobs:
    def __init__(self) -> None:
        self.calls = []

    async def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> Job:
        self.calls.append(
            (tenant_id, job_id)
        )

        return Job(
            id=job_id,
            tenant_id=tenant_id,
            title="Senior Backend Engineer",
            company="Example Corp",
            location="Remote",
            description="Build Python backend systems.",
            source="greenhouse",
            source_job_id="source-1",
            source_url="https://boards.greenhouse.io/example/jobs/source-1",
        )


def test_job_lookup_tool_exposes_typed_read_only_contract():
    tool = build_job_lookup_tool()

    assert tool["type"] == "function"
    assert tool["function"]["name"] == JOB_LOOKUP_TOOL_NAME

    description = tool["function"]["description"].lower()

    assert "read" in description
    assert "canonical" in description
    assert "read-only" in description

    properties = tool["function"]["parameters"]["properties"]

    assert set(properties) == {
        "tenant_id",
        "job_id",
    }


def test_job_lookup_handler_returns_authoritative_job():
    repository = FakeCanonicalJobs()
    handler = create_job_lookup_handler(
        repository
    )

    raw = handler(
        JOB_LOOKUP_TOOL_NAME,
        {
            "tenant_id": TENANT_ID,
            "job_id": JOB_ID,
        },
    )

    payload = json.loads(raw)

    assert repository.calls == [
        (TENANT_ID, JOB_ID)
    ]

    assert payload["job"]["id"] == JOB_ID
    assert payload["job"]["tenant_id"] == TENANT_ID
    assert (
        payload["job"]["title"]
        == "Senior Backend Engineer"
    )
    assert (
        payload["job"]["description"]
        == "Build Python backend systems."
    )
