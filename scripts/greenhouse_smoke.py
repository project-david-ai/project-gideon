
from __future__ import annotations

import os

from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
)
from project_gideon.models.delegation import (
    JobsDelegationAction,
    JobsDelegationRequest,
)


token = os.environ.get(
    "GIDEON_GREENHOUSE_BOARD_TOKEN"
)

if not token:
    raise SystemExit(
        "Set GIDEON_GREENHOUSE_BOARD_TOKEN first."
    )

company = os.environ.get(
    "GIDEON_GREENHOUSE_COMPANY"
)

adapter = GreenhouseJobAcquisitionPort()

request = JobsDelegationRequest(
    tenant_id="greenhouse-smoke",
    action=JobsDelegationAction.DISCOVER,
    source="greenhouse",
    parameters={
        "boards": [
            {
                "token": token,
                "company": company,
            }
        ],
        "max_jobs_per_board": 5,
    },
)

candidates = adapter.discover(
    request
)

print(
    f"GREENHOUSE_LIVE_JOBS={len(candidates)}"
)

for candidate in candidates:
    job = candidate.job

    print(
        f"{job.source_job_id} | "
        f"{job.company} | "
        f"{job.title} | "
        f"{job.location or '-'}"
    )

print(
    "GREENHOUSE_STRUCTURED_SOURCE=PASS"
)
