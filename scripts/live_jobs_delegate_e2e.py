from __future__ import annotations

import os
from typing import Any

from project_gideon.integrations.jobs.async_ingestion import (
    ThreadedJobIngestionExecutor,
)
from project_gideon.integrations.jobs.ats_routing import (
    ATSRegistrationJobAcquisitionRouter,
)
from project_gideon.integrations.jobs.delegation import (
    GideonJobsDelegationPort,
)
from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
)
from project_gideon.integrations.jobs.greenhouse_discovery import (
    GreenhouseATSDetector,
)
from project_gideon.integrations.jobs.greenhouse_registration_acquisition import (
    GreenhouseRegistrationAcquisitionAdapter,
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
from project_gideon.models import (
    ApplicationState,
    CandidateIdentity,
    CandidateProfile,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationAction,
    JobsDelegationRequest,
)
from project_gideon.repositories import (
    InMemoryApplicationRepository,
    InMemoryCandidateRepository,
)
from project_gideon.repositories.job_ingestion_memory import (
    InMemoryJobIngestionRepository,
)
from project_gideon.services.ats_discovery import (
    ATSDiscoveryService,
)
from project_gideon.services.application_campaign import (
    ApplicationCampaignService,
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


class CanonicalJobReadAdapter:
    """
    Expose the authoritative ingestion repository through the read contract
    consumed by ApplicationCampaignService.

    This adapter owns no state. Reads are delegated to the same canonical
    repository populated by JobIngestionService.
    """

    def __init__(
        self,
        repository: InMemoryJobIngestionRepository,
    ) -> None:
        self._repository = repository

    async def get(
        self,
        job_id: str,
        tenant_id: str,
    ):
        return await self._repository.get(
            tenant_id=tenant_id,
            job_id=job_id,
        )

    async def list_for_tenant(
        self,
        tenant_id: str,
    ):
        return await self._repository.list_for_tenant(
            tenant_id
        )


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

    greenhouse_acquisition = (
        GreenhouseJobAcquisitionPort()
    )

    ats_discovery = ATSDiscoveryService(
        detectors=[
            GreenhouseATSDetector(),
        ]
    )

    acquisition = (
        ATSRegistrationJobAcquisitionRouter(
            discovery=ats_discovery,
            providers=[
                GreenhouseRegistrationAcquisitionAdapter(
                    greenhouse_acquisition
                ),
            ],
        )
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

    candidate_repository = (
        InMemoryCandidateRepository()
    )

    application_repository = (
        InMemoryApplicationRepository()
    )

    canonical_jobs = CanonicalJobReadAdapter(
        repository
    )

    campaign_service = ApplicationCampaignService(
        jobs=canonical_jobs,
        candidates=candidate_repository,
        applications=application_repository,
    )

    campaign_tenant_id = (
        "gideon-live-e2e-supervisor"
    )

    candidate = CandidateProfile(
        id="candidate-live-e2e",
        tenant_id=campaign_tenant_id,
        identity=CandidateIdentity(
            first_name="Live",
            last_name="Candidate",
            email="live-candidate@example.com",
        ),
    )

    import asyncio

    asyncio.run(
        candidate_repository.save(
            candidate
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
                query="Current jobs at Stripe",
                employers=[
                    {
                        "company_name": "Stripe",
                        "domain": "stripe.com",
                    }
                ],
                max_jobs_per_employer=5,
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
                campaign_service=campaign_service,
            )
        )

        prompt = """
Find up to 3 current jobs at Stripe.

Use jobs_delegate for discovery.

The tenant_id must be "gideon-live-e2e-supervisor".
Use a typed employer target for Stripe.
Do not guess or supply an ATS provider, board token, or provider-specific
source identifier. The jobs faction must resolve Stripe's recruiting source.

After jobs_delegate returns canonical job IDs:

1. Select the first canonical job ID returned.
2. Use application_campaign with action "shortlist".
3. Use candidate_id "candidate-live-e2e".
4. Use application_campaign again with action "start_preparation" using
   the application ID returned by the shortlist operation.

Do not use research_delegate, web search, or browser automation.

After both campaign operations complete, report the canonical job ID,
application ID, and final authoritative application state.
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

        campaign_calls = [
            tool_call
            for tool_call
            in turn.tool_calls
            if (
                tool_call.tool_name
                == "application_campaign"
            )
        ]

        if len(campaign_calls) < 2:
            raise RuntimeError(
                "Supervisor did not execute both "
                "application campaign operations."
            )

        if not all(
            tool_call.executed
            for tool_call
            in campaign_calls
        ):
            raise RuntimeError(
                "One or more application_campaign "
                "calls were not executed."
            )

        if not turn.content.strip():
            raise RuntimeError(
                "Supervisor did not continue "
                "after campaign operations."
            )

        applications = asyncio.run(
            application_repository.list_for_tenant(
                campaign_tenant_id
            )
        )

        if len(applications) != 1:
            raise RuntimeError(
                "Expected exactly one durable application "
                f"campaign, found {len(applications)}."
            )

        durable_application = applications[0]

        if (
            durable_application.state
            is not ApplicationState.PREPARING
        ):
            raise RuntimeError(
                "Durable application did not reach PREPARING. "
                f"state={durable_application.state.value}"
            )

        if (
            durable_application.candidate_id
            != "candidate-live-e2e"
        ):
            raise RuntimeError(
                "Durable application candidate mismatch."
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
            "SUPERVISOR_CAMPAIGN_TOOL_CALLS="
            f"{len(campaign_calls)}"
        )

        print(
            "DURABLE_APPLICATION_ID="
            f"{durable_application.id}"
        )

        print(
            "DURABLE_APPLICATION_JOB_ID="
            f"{durable_application.job_id}"
        )

        print(
            "DURABLE_APPLICATION_STATE="
            f"{durable_application.state.value}"
        )

        print(
            "SUPERVISOR_CAMPAIGN_STATE=PASS"
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
            "LIVE_JOBS_CAMPAIGN_E2E=PASS"
        )

    finally:
        ingestion_executor.close()


if __name__ == "__main__":
    main()
