from __future__ import annotations

import os
from typing import Any

from project_gideon.integrations.jobs.async_ingestion import (
    ThreadedJobIngestionExecutor,
)
from project_gideon.integrations.jobs.delegation import (
    GideonJobsDelegationPort,
)
from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
)
from project_gideon.integrations.project_david.bootstrap import (
    ProjectDavidBootstrap,
)
from project_gideon.integrations.project_david.client import (
    ProjectDavidClientFactory,
)
from project_gideon.integrations.project_david.config import (
    load_project_david_config,
)
from project_gideon.integrations.project_david.supervisor_runtime import (
    ProjectDavidConfig,
    build_supervisor_session_service,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationRequest,
)
from project_gideon.repositories.job_ingestion_memory import (
    InMemoryJobIngestionRepository,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


def require_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)

        if value:
            return value

    raise RuntimeError(
        "Missing required environment value. "
        f"Tried: {', '.join(names)}"
    )


def optional_env(
    *names: str,
) -> str | None:
    for name in names:
        value = os.environ.get(name)

        if value:
            return value

    return None


def resolve_runtime_bindings(
    *,
    client: Any,
    config: ProjectDavidConfig,
) -> Any:
    """
    Use Gideon's real production startup reconciliation path.
    """

    bindings = ProjectDavidBootstrap(
        client=client,
        config=config,
    ).reconcile()

    if not bindings.meta_data.get(
        "ready",
        False,
    ):
        raise RuntimeError(
            "Project David bootstrap completed "
            "without ready state."
        )

    print(
        "STARTUP_BINDINGS_SOURCE="
        "ProjectDavidBootstrap.reconcile"
    )

    return bindings


def main() -> None:
    print(
        "LIVE_JOBS_DELEGATE_E2E=START"
    )

    # --------------------------------------------------------
    # DOMAIN / JOBS FACTION
    # --------------------------------------------------------

    repository = (
        InMemoryJobIngestionRepository()
    )

    ingestion_service = (
        JobIngestionService(
            repository
        )
    )

    ingestion_executor = (
        ThreadedJobIngestionExecutor(
            ingestion_service
        )
    )

    acquisition = (
        GreenhouseJobAcquisitionPort()
    )

    jobs_port = (
        GideonJobsDelegationPort(
            acquisition=acquisition,
            ingestion=ingestion_executor,
        )
    )

    jobs_service = (
        JobsDelegationService(
            jobs_port
        )
    )

    try:
        # ----------------------------------------------------
        # PROOF 1:
        # REAL SOURCE → JOBS FACTION → CANONICAL INGESTION
        # ----------------------------------------------------

        direct_request = (
            JobsDelegationRequest(
                tenant_id="gideon-live-e2e",
                action=JobsDelegationAction.DISCOVER,
                query=(
                    "Discover a small sample "
                    "of Stripe jobs."
                ),
                source="greenhouse",
                parameters={
                    "boards": [
                        {
                            "token": "stripe",
                            "company": "Stripe",
                        }
                    ],
                    "max_jobs_per_board": 5,
                },
            )
        )

        direct_result = (
            jobs_service.delegate(
                direct_request
            )
        )

        if (
            direct_result.status
            != DelegationStatus.SUCCEEDED
        ):
            raise RuntimeError(
                "Direct jobs faction failed: "
                f"{direct_result.error}"
            )

        if (
            direct_result.discovered_count
            < 1
        ):
            raise RuntimeError(
                "Live Greenhouse discovery "
                "returned no jobs."
            )

        if (
            direct_result.ingested_count
            < 1
        ):
            raise RuntimeError(
                "Authoritative ingestion created "
                "no canonical jobs."
            )

        if not direct_result.job_ids:
            raise RuntimeError(
                "No canonical job IDs returned."
            )

        print(
            "DIRECT_JOBS_FACTION=PASS"
        )

        print(
            "DIRECT_DISCOVERED="
            f"{direct_result.discovered_count}"
        )

        print(
            "DIRECT_INGESTED="
            f"{direct_result.ingested_count}"
        )

        print(
            "DIRECT_DUPLICATES="
            f"{direct_result.duplicate_count}"
        )

        print(
            "DIRECT_CANONICAL_JOB_IDS="
            + ",".join(
                direct_result.job_ids
            )
        )

        # Repeat the identical request to prove canonical
        # duplicate authority is below the acquisition layer.

        duplicate_result = (
            jobs_service.delegate(
                direct_request
            )
        )

        if (
            duplicate_result.status
            != DelegationStatus.SUCCEEDED
        ):
            raise RuntimeError(
                "Duplicate proof request failed."
            )

        if (
            duplicate_result.ingested_count
            != 0
        ):
            raise RuntimeError(
                "Repeated source records created "
                "new canonical jobs."
            )

        if (
            duplicate_result.duplicate_count
            != direct_result.discovered_count
        ):
            raise RuntimeError(
                "Repeated source records were not "
                "reported as canonical duplicates."
            )

        print(
            "AUTHORITATIVE_DUPLICATE_PROOF=PASS"
        )

        # ----------------------------------------------------
        # PROOF 2:
        # SUPERVISOR → jobs_delegate → SAME JOBS FACTION
        # ----------------------------------------------------

        config = load_project_david_config()

        client_factory = (
            ProjectDavidClientFactory(
                config
            )
        )

        client = (
            client_factory.create()
        )

        bindings = resolve_runtime_bindings(
            client=client,
            config=config,
        )

        supervisor = (
            build_supervisor_session_service(
                client=client,
                client_factory=client_factory,
                config=config,
                bindings=bindings,
                jobs_service=jobs_service,
            )
        )

        prompt = """
Use the jobs_delegate capability.

Discover jobs from the Greenhouse source for Stripe.

Use exactly these source parameters:
{
  "boards": [
    {
      "token": "stripe",
      "company": "Stripe"
    }
  ],
  "max_jobs_per_board": 3
}

The tenant_id must be "gideon-live-e2e-supervisor".

Do not use web search or browser automation for this request.
After the tool completes, briefly tell me how many canonical jobs
were returned.
""".strip()

        turn = supervisor.run(
            prompt=prompt,
            meta_data={
                "test": (
                    "live_greenhouse_"
                    "jobs_delegate_e2e"
                ),
                "gideon_faction": "career",
            },
        )

        jobs_calls = [
            tool_call
            for tool_call
            in turn.tool_calls
            if (
                tool_call.tool_name
                == "jobs_delegate"
            )
        ]

        if not jobs_calls:
            raise RuntimeError(
                "Supervisor did not invoke jobs_delegate."
            )

        if not any(
            tool_call.executed
            for tool_call
            in jobs_calls
        ):
            raise RuntimeError(
                "jobs_delegate was requested "
                "but not executed."
            )

        if not turn.content.strip():
            raise RuntimeError(
                "Supervisor did not continue "
                "after jobs_delegate."
            )

        print(
            "SUPERVISOR_JOBS_DELEGATE=PASS"
        )

        print(
            "SUPERVISOR_JOBS_TOOL_CALLS="
            f"{len(jobs_calls)}"
        )

        print(
            "SUPERVISOR_TURN_N_CONTINUATION=PASS"
        )

        print(
            "SUPERVISOR_RESPONSE="
            + turn.content.replace(
                "\n",
                " ",
            )[:500]
        )

        print(
            "LIVE_EXTERNAL_SOURCE=greenhouse"
        )

        print(
            "LIVE_EMPLOYER=Stripe"
        )

        print(
            "BROWSER_AUTOMATION=NO"
        )

        print(
            "LIVE_JOBS_DELEGATE_E2E=PASS"
        )

    finally:
        ingestion_executor.close()


if __name__ == "__main__":
    main()
