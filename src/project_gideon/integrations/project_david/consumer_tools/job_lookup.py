from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

from project_gideon.models.job import Job
from project_gideon.models.job_lookup import (
    JobLookupRequest,
    JobLookupResult,
)


JOB_LOOKUP_TOOL_NAME = "job_lookup"


class CanonicalJobReader(Protocol):
    async def get(
        self,
        *,
        tenant_id: str,
        job_id: str,
    ) -> Job:
        ...


def build_job_lookup_tool() -> dict[str, Any]:
    """Project David function declaration for canonical job reads."""

    return {
        "type": "function",
        "function": {
            "name": JOB_LOOKUP_TOOL_NAME,
            "description": (
                "Read one authoritative canonical Job by tenant_id and job_id. "
                "Use this after jobs_delegate returns canonical job identifiers "
                "when you need the job title, company, description, location, "
                "requirements, or other canonical fields for fit reasoning. "
                "This tool is read-only and does not discover or ingest jobs."
            ),
            "parameters": JobLookupRequest.model_json_schema(),
        },
    }


def _run_job_lookup(operation):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(operation())

    raise RuntimeError(
        "Job lookup consumer tool requires Project David's synchronous "
        "consumer-tool execution context."
    )


def create_job_lookup_handler(
    repository: CanonicalJobReader,
) -> Callable[[str, dict[str, Any]], str]:
    """Build the synchronous handler for authoritative canonical job reads."""

    def handle(
        tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        if tool_name != JOB_LOOKUP_TOOL_NAME:
            raise ValueError(
                f"Job lookup handler cannot execute tool={tool_name!r}."
            )

        request = JobLookupRequest.model_validate(arguments)

        job = _run_job_lookup(
            lambda: repository.get(
                tenant_id=request.tenant_id,
                job_id=request.job_id,
            )
        )

        return JobLookupResult(
            job=job,
        ).model_dump_json(
            exclude_none=True
        )

    return handle
