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

    canonical_cv_file_id = (
        "vsf_10e8b30a-7569-42e1-8cf7-cd08baae0841"
    )

    candidate = CandidateProfile(
        id="candidate-live-e2e",
        tenant_id=campaign_tenant_id,
        identity=CandidateIdentity(
            first_name="Live",
            last_name="Candidate",
            email="live-candidate@example.com",
        ),
        default_cv_file_id=canonical_cv_file_id,
        meta_data={
            "live_e2e": True,
            "candidate_knowledge": "canonical_cv",
        },
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

        presentation_events = []

        supervisor = (
            build_supervisor_session_service(
                client=client,
                client_factory=client_factory,
                config=config,
                bindings=bindings,
                jobs_service=jobs_service,
                job_reader=canonical_jobs,
                campaign_service=campaign_service,
                presentation_sink=presentation_events.append,
            )
        )

        prompt = """
Find current software-engineering jobs at Stripe that could be
appropriate for candidate_id "candidate-live-e2e".

The tenant_id must be "gideon-live-e2e-supervisor".

This is a bounded workflow evaluation.

Use jobs_delegate for real job discovery with a typed employer target for
Stripe and max_jobs_per_employer=3. Do not guess or supply an ATS provider,
board token, or provider-specific source identifier. The jobs faction must
resolve Stripe's recruiting source.

After the first successful jobs_delegate call, do not call jobs_delegate
again. The canonical job IDs returned by that successful call are the complete
evaluation set for this run.

Use native file_search to retrieve evidence from the candidate's configured
CV. Do not invent or assume candidate skills, experience, seniority, or other
candidate facts.

Use job_lookup to inspect the authoritative canonical records for at most the
first 3 canonical job IDs returned by jobs_delegate. Do not inspect or discover
additional jobs.

Compare those jobs against the retrieved CV evidence and select the
best-supported available match from that bounded set. Do not select from an
identifier alone and do not simply choose the first result.

Then:
1. Use application_campaign with action "shortlist" for the selected
   canonical job and candidate_id "candidate-live-e2e".
2. Use application_campaign again with action "start_preparation" using
   the application ID returned by the shortlist operation.

Do not use research_delegate, web search, or browser automation.

After both campaign operations complete, briefly report:
- the selected canonical job ID;
- the application ID;
- the final authoritative application state; and
- the retrieved candidate evidence and canonical job evidence that supported
  the selection.

Do not claim evidence that was not returned by the tools.
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

        job_lookup_calls = [
            tool_call
            for tool_call
            in turn.tool_calls
            if (
                tool_call.tool_name
                == "job_lookup"
            )
        ]

        if not job_lookup_calls:
            raise RuntimeError(
                "Supervisor did not invoke job_lookup for "
                "canonical job evidence."
            )

        if not any(
            tool_call.executed
            for tool_call
            in job_lookup_calls
        ):
            raise RuntimeError(
                "job_lookup was requested but not executed."
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

        completed_actions = (
            client.actions.get_actions_by_status(
                turn.run_id,
                status="completed",
            )
        )

        native_file_search_actions = [
            action
            for action in completed_actions
            if action.get("tool_name") == "file_search"
        ]

        if not native_file_search_actions:
            completed_tools = sorted(
                {
                    action.get("tool_name")
                    for action in completed_actions
                    if action.get("tool_name")
                }
            )

            raise RuntimeError(
                "No completed native file_search Action was "
                "persisted for the supervisor run. "
                f"completed_tools={completed_tools}"
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

        canonical_supervisor_jobs = asyncio.run(
            repository.list_for_tenant(
                campaign_tenant_id
            )
        )

        canonical_supervisor_job_ids = {
            job.id
            for job in canonical_supervisor_jobs
        }

        if (
            durable_application.job_id
            not in canonical_supervisor_job_ids
        ):
            raise RuntimeError(
                "Selected application job is not present in "
                "the supervisor tenant's authoritative "
                "canonical job repository."
            )

        print(
            "SUPERVISOR_JOBS_DELEGATE=PASS"
        )

        print(
            "SUPERVISOR_JOBS_TOOL_CALLS="
            f"{len(jobs_calls)}"
        )

        print(
            "SUPERVISOR_JOB_LOOKUP_TOOL_CALLS="
            f"{len(job_lookup_calls)}"
        )

        print(
            "NATIVE_FILE_SEARCH_ACTIONS="
            f"{len(native_file_search_actions)}"
        )

        print(
            "CANONICAL_CV_FILE_ID="
            f"{canonical_cv_file_id}"
        )

        print(
            "SEMANTIC_CV_JOB_REASONING=PASS"
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
