from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from project_gideon.services.candidate_profile_context import (
    apply_candidate_profile_context,
    load_candidate_profile_context,
    render_candidate_profile_instructions,
)
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
from project_gideon.integrations.project_david.native_preparation_evidence import (
    ProjectDavidNativePreparationEvidence,
)
from project_gideon.integrations.project_david.supervisor_runtime import (
    build_supervisor_session_service,
)
from project_gideon.models import (
    ApplicationState,
    CandidateIdentity,
    CandidateProfile,
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
from project_gideon.services.canonical_cv_artifact import (
    ensure_canonical_cv_artifact,
)
from project_gideon.services.canonical_cv_staging import (
    CanonicalApplicationFileStager,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)
from project_gideon.services.native_application_preparation import (
    NativeApplicationPreparationCoordinator,
)


TENANT_ID = "gideon-real-application"
CANDIDATE_ID = "candidate-francis-real"

# Keep Gideon's outer inactivity watchdog strictly longer than
# the maximum legitimate wait for one Project David inference
# stream chunk. The SDK currently uses 280 seconds per chunk.
INFERENCE_CHUNK_TIMEOUT_SECONDS = 280.0
WATCHDOG_GRACE_SECONDS = 620.0
WATCHDOG_IDLE_TIMEOUT_SECONDS = (
    INFERENCE_CHUNK_TIMEOUT_SECONDS
    + WATCHDOG_GRACE_SECONDS
)

# Canonical RAG identity remains the vector-store file.
CANONICAL_CV_VECTOR_STORE_ID = (
    "vect_x9pQWTKSS6H6JiJSu5mT4I"
)

CANONICAL_CV_VECTOR_FILE_ID = (
    "vsf_10e8b30a-7569-42e1-8cf7-cd08baae0841"
)

# Browser upload bytes use a distinct Project David Files API object.
CANONICAL_CV_ARTIFACT_BINDING = (
    Path(".local/canonical-cv-artifact.json")
)

CANONICAL_CV_SOURCE = Path(
    r"C:\Users\franc\OneDrive\Documents\Misc\Francis_Neequaye_Software_Engineer_CV (3).docx"
)


def load_canonical_cv_artifact_file_id(
    file_client,
) -> str:
    return ensure_canonical_cv_artifact(
        file_client=file_client,
        binding_path=CANONICAL_CV_ARTIFACT_BINDING,
        source_path=CANONICAL_CV_SOURCE,
        expected_vector_store_id=(
            CANONICAL_CV_VECTOR_STORE_ID
        ),
        expected_vector_file_id=(
            CANONICAL_CV_VECTOR_FILE_ID
        ),
    )


class CanonicalJobReadAdapter:
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


def field(obj: Any, name: str, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def main() -> None:
    load_dotenv(Path(".env"))

    # Resolve Project David before constructing the candidate because the
    # browser-upload Files object is deliberately ephemeral and may need
    # byte-identical regeneration.
    config = load_project_david_config()

    client_factory = ProjectDavidClientFactory(
        config
    )

    client = client_factory.create()

    canonical_cv_artifact_file_id = (
        load_canonical_cv_artifact_file_id(
            client.files
        )
    )

    print("REAL_APPLICATION_PREPARATION=START")
    print(f"TENANT_ID={TENANT_ID}")
    print(f"CANDIDATE_ID={CANDIDATE_ID}")
    print(
        "CANONICAL_CV_VECTOR_FILE_ID="
        + CANONICAL_CV_VECTOR_FILE_ID
    )
    print(
        "CANONICAL_CV_ARTIFACT_FILE_ID="
        + canonical_cv_artifact_file_id
    )

    # ---------------------------------------------------------
    # JOB DOMAIN
    # ---------------------------------------------------------

    job_repository = InMemoryJobIngestionRepository()

    ingestion_service = JobIngestionService(
        job_repository
    )

    ingestion_executor = ThreadedJobIngestionExecutor(
        ingestion_service
    )

    try:
        greenhouse = GreenhouseJobAcquisitionPort()

        ats_discovery = ATSDiscoveryService(
            detectors=[
                GreenhouseATSDetector(),
            ]
        )

        acquisition = ATSRegistrationJobAcquisitionRouter(
            discovery=ats_discovery,
            providers=[
                GreenhouseRegistrationAcquisitionAdapter(
                    greenhouse
                ),
            ],
        )

        jobs_port = GideonJobsDelegationPort(
            acquisition=acquisition,
            ingestion=ingestion_executor,
        )

        jobs_service = JobsDelegationService(
            jobs_port
        )

        canonical_jobs = CanonicalJobReadAdapter(
            job_repository
        )

        # -----------------------------------------------------
        # CANDIDATE / CAMPAIGN
        # -----------------------------------------------------

        profile_context = load_candidate_profile_context(
            Path("config/candidate_profile.yaml")
        )

        profile_instructions = (
            render_candidate_profile_instructions(
                profile_context
            )
        )

        candidate_repository = (
            InMemoryCandidateRepository()
        )

        application_repository = (
            InMemoryApplicationRepository()
        )

        candidate = CandidateProfile(
            id=CANDIDATE_ID,
            tenant_id=TENANT_ID,
            identity=CandidateIdentity(
                first_name="Francis",
                last_name="Neequaye",
                email="francis.neequaye@gmail.com",
                phone="+44 7427 348 836",
                # Deliberately do not use the old UK CV address as
                # authoritative current location.
                location=None,
            ),
            default_cv_file_id=canonical_cv_artifact_file_id,
            meta_data={
                "real_candidate": True,
                "candidate_knowledge": "canonical_cv",
                "canonical_cv_vector_store_id": (
                    CANONICAL_CV_VECTOR_STORE_ID
                ),
                "canonical_cv_vector_file_id": (
                    CANONICAL_CV_VECTOR_FILE_ID
                ),
            },
        )

        candidate = apply_candidate_profile_context(
            candidate,
            profile_context,
        )

        asyncio.run(
            candidate_repository.save(
                candidate
            )
        )

        campaign_service = ApplicationCampaignService(
            jobs=canonical_jobs,
            candidates=candidate_repository,
            applications=application_repository,
        )

        # -----------------------------------------------------
        # PROJECT DAVID RUNTIME
        # -----------------------------------------------------

        cv_stager = CanonicalApplicationFileStager(
            file_client=client.files,
            staging_root=Path(".local/playwright-uploads"),
        )

        bindings = ProjectDavidBootstrap(
            client=client,
            config=config,
        ).reconcile()

        if not bindings.meta_data.get(
            "ready",
            False,
        ):
            raise RuntimeError(
                "Project David bootstrap did not reach ready state."
            )

        print(
            "PROJECT_DAVID_BOOTSTRAP=PASS"
        )
        print(
            "PLAYWRIGHT_ATTACHED_COUNT="
            + str(
                bindings.meta_data.get(
                    "playwright_attached_count"
                )
            )
        )

        evidence = (
            ProjectDavidNativePreparationEvidence(
                client=client,
                bindings=bindings,
            )
        )

        preparation_coordinator = (
            NativeApplicationPreparationCoordinator(
                applications=application_repository,
                jobs=canonical_jobs,
                candidates=candidate_repository,
                evidence=evidence,
                file_stager=cv_stager,
                cv_file_resolver=lambda: load_canonical_cv_artifact_file_id(
                    client.files
                ),
            )
        )

        watchdog_lock = threading.Lock()

        watchdog_state = {
            "run_id": None,
            "timer": None,
            "generation": 0,
        }

        def cancel_timeout(
            generation: int,
        ) -> None:
            with watchdog_lock:
                if (
                    generation
                    != watchdog_state["generation"]
                ):
                    return

                run_id = watchdog_state["run_id"]

                if not run_id:
                    return

                watchdog_state["timer"] = None

            print(
                "WATCHDOG_IDLE_TIMEOUT_RUN_ID="
                + run_id,
                flush=True,
            )

            try:
                client.runs.cancel_run(
                    run_id
                )
            except Exception:
                pass

        def refresh_watchdog() -> None:
            with watchdog_lock:
                run_id = watchdog_state["run_id"]

                if not run_id:
                    return

                previous = watchdog_state["timer"]

                watchdog_state["generation"] += 1

                generation = (
                    watchdog_state["generation"]
                )

                watchdog = threading.Timer(
                    WATCHDOG_IDLE_TIMEOUT_SECONDS,
                    cancel_timeout,
                    args=(generation,),
                )

                watchdog.daemon = True

                watchdog_state["timer"] = watchdog

                if previous is not None:
                    previous.cancel()

                watchdog.start()

        def arm_watchdog(
            run_id: str,
        ) -> None:
            with watchdog_lock:
                if watchdog_state["run_id"] is not None:
                    raise RuntimeError(
                        "Supervisor watchdog was armed more than once."
                    )

                watchdog_state["run_id"] = run_id

            refresh_watchdog()

            print(
                f"WATCHDOG_ARMED_RUN_ID={run_id}",
                flush=True,
            )

        def stop_watchdog() -> None:
            with watchdog_lock:
                watchdog = watchdog_state["timer"]

                watchdog_state["generation"] += 1
                watchdog_state["timer"] = None

            if watchdog is not None:
                watchdog.cancel()

        if (
            WATCHDOG_IDLE_TIMEOUT_SECONDS
            <= INFERENCE_CHUNK_TIMEOUT_SECONDS
        ):
            raise RuntimeError(
                "Watchdog inactivity timeout must exceed "
                "the inference per-chunk timeout."
            )

        supervisor = (
            build_supervisor_session_service(
                client=client,
                client_factory=client_factory,
                config=config,
                bindings=bindings,
                jobs_service=jobs_service,
                job_reader=canonical_jobs,
                campaign_service=campaign_service,
                preparation_coordinator=(
                    preparation_coordinator
                ),
                max_turns=32,
                blocked_consumer_tool_names=(
                    "research_delegate",
                ),
                inference_chunk_timeout_seconds=(
                    INFERENCE_CHUNK_TIMEOUT_SECONDS
                ),
                on_run_created=arm_watchdog,
                on_activity=refresh_watchdog,
            )
        )

        # -----------------------------------------------------
        # REAL END-TO-END REQUEST
        #
        # Gideon itself:
        #   1. discovers real jobs;
        #   2. reads canonical job records;
        #   3. retrieves Francis's CV;
        #   4. chooses the strongest match;
        #   5. creates the application campaign;
        #   6. starts preparation;
        #   7. drives native Playwright;
        #   8. stops before submission.
        # -----------------------------------------------------

        prompt = f"""
This is a REAL application-preparation run for the candidate
Francis Neequaye.

Tenant ID:
{TENANT_ID}

Candidate ID:
{CANDIDATE_ID}

Use Gideon's normal production capabilities.

1. Discover up to 3 CURRENT software/backend/platform/
   infrastructure/AI-engineering jobs at Stripe.

   Use jobs_delegate.

   Supply Stripe as the employer with corporate domain
   stripe.com. Do not invent an ATS provider or board ID;
   let the jobs faction resolve it.

2. The FIRST successful jobs_delegate result is the complete
   bounded discovery set for this run.

   Do not call jobs_delegate again. Do not widen the search.

   For every canonical job ID in that result, use job_lookup
   to inspect the authoritative canonical job.

   If none of those bounded canonical jobs is a defensible
   match, stop and report that no defensible match was found.
   Do not create an application merely to satisfy the test.

3. Use native file_search against the attached canonical
   candidate knowledge to evaluate Francis's actual CV
   evidence against those jobs.

4. Select ONE strongest defensible match based only on the
   canonical job data and candidate evidence.

   IMPORTANT TERMINAL-CONDITION RULE:

   If a strongest defensible match exists, DO NOT stop after
   reporting or narrating the fit analysis.

   Fit-analysis prose is intermediate work, not completion.

   Your next action after identifying that match MUST be
   application_campaign "shortlist".

   You may stop before creating an application only when none
   of the bounded canonical jobs is a defensible match.

5. Use application_campaign action "shortlist" with:
   tenant_id="{TENANT_ID}"
   candidate_id="{CANDIDATE_ID}"
   and the selected canonical job_id.

6. Use application_campaign action "start_preparation" on
   the resulting application_id.

7. Call application_prepare using ONLY the authoritative
   application_id and tenant_id.

8. When application_prepare returns
   next_action="use_native_playwright":

   - navigate to the exact application_url returned by
     application_prepare;
   - inspect the real form with native browser_snapshot;
   - fill factual fields automatically where authoritative
     candidate/package/CV evidence supplies the answer;
   - use current snapshot refs for interactions; never invent
     CSS/XPath/iframe selectors;
   - do not send combobox controls through browser_fill_form;
   - when the snapshot identifies a control as role=combobox
      but its option labels are not visible, call
      browser_inspect_combobox_options using that current ref;
   - use the inspector's returned exact visible option labels as
      browser evidence;
   - if an authoritative candidate value is not among those
      visible labels and the combobox is searchable, obtain a
      current ref and call browser_inspect_combobox_options again
      with query set exactly to that authoritative candidate value;
   - query is discovery-only; it is never selection authority;
   - call browser_select_combobox_option only after inspection has
      browser-observed the exact visible label to select;
   - never infer, normalize, abbreviate, or enrich exactOption
      from candidate facts alone;
   - browser_select_option is only for a native HTML <select>
     element. Never send a role=combobox control through
     browser_select_option;
   - select factual dropdown/radio values when supported by
     authoritative evidence;
   - when package.meta_data.cv_playwright_path is present
     and the form exposes the candidate CV upload control,
     call browser_upload_candidate_file with path set to that
     exact /uploads/... value;
   - never construct, infer, or translate a host filesystem
     path from cv_file_id;
   - never invent candidate facts.

9. After the LAST browser mutation, call browser_snapshot
   with NO arguments: no target, ref, filename, or depth.
   It must return one full inline accessibility tree.
   Do not perform another browser mutation after that snapshot.
   Call application_prepare immediately so Gideon's durable
   state reconciles against that fresh evidence.

10. If application_prepare returns pending_fields, fill
    ONLY those for which it supplied authoritative prepared
    answers. Snapshot and reconcile again.

11. If the real employer form asks a personal/narrative
    question that requires Francis's own answer, DO NOT
    generate an answer. Leave it unresolved so the
    application becomes NEEDS_INPUT.

12. ABSOLUTE SAFETY BOUNDARY:
    - do not submit the application;
    - do not approve the application;
    - do not click a submit/apply/final confirmation button;
    - do not execute JavaScript;
    - do not invent answers merely to reach a terminal state.

Stop only when Gideon's durable application reaches either:
READY_FOR_REVIEW or NEEDS_INPUT.

Report the selected job, application ID, final durable state,
and unresolved questions if any.
""".strip()

        prompt = (
            profile_instructions
            + "\n\n"
            + prompt
        )

        print(
            "\n=== REAL SUPERVISOR RUN ===",
            flush=True,
        )

        try:
            turn = supervisor.run(
                prompt=prompt,
                meta_data={
                    "tenant_id": TENANT_ID,
                    "mode": "real_application_prepare",
                    "submission_allowed": False,
                },
            )

        finally:
            stop_watchdog()

        print(
            f"SUPERVISOR_RUN_ID={turn.run_id}"
        )

        # -----------------------------------------------------
        # DURABLE DOMAIN RESULT
        # -----------------------------------------------------

        applications = asyncio.run(
            application_repository.list_for_tenant(
                TENANT_ID
            )
        )

        if not applications:
            raise RuntimeError(
                "Supervisor created no application campaign."
            )

        if len(applications) != 1:
            raise RuntimeError(
                "Expected exactly one real application; "
                f"found {len(applications)}."
            )

        application = applications[0]

        job = asyncio.run(
            canonical_jobs.get(
                application.job_id,
                TENANT_ID,
            )
        )

        print(
            "SELECTED_JOB_ID="
            + application.job_id
        )
        print(
            "SELECTED_JOB_TITLE="
            + str(field(job, "title"))
        )
        print(
            "SELECTED_JOB_COMPANY="
            + str(field(job, "company"))
        )
        print(
            "APPLICATION_ID="
            + application.id
        )
        print(
            "FINAL_APPLICATION_STATE="
            + application.state.value
        )

        unresolved = getattr(
            application,
            "unresolved_questions",
            [],
        ) or []

        print(
            "UNRESOLVED_REQUIRED_QUESTIONS="
            + str(len(unresolved))
        )

        if unresolved:
            print(
                "UNRESOLVED_QUESTIONS="
                + json.dumps(
                    [
                        (
                            item.model_dump()
                            if hasattr(
                                item,
                                "model_dump",
                            )
                            else item
                        )
                        for item in unresolved
                    ],
                    default=str,
                )
            )

        print(
            "APPLICATION_SUBMITTED="
            + (
                "YES"
                if application.submitted_at
                else "NO"
            )
        )

        if application.submitted_at is not None:
            raise RuntimeError(
                "SAFETY FAILURE: application was submitted."
            )

        allowed_terminal = {
            ApplicationState.READY_FOR_REVIEW,
            ApplicationState.NEEDS_INPUT,
        }

        if application.state not in allowed_terminal:
            raise RuntimeError(
                "Real application did not reach a safe "
                "pre-submission terminal state: "
                f"{application.state.value}"
            )

        # -----------------------------------------------------
        # PROJECT DAVID ACTION AUDIT
        # -----------------------------------------------------

        from project_gideon.integrations.project_david.action_reconciliation import (
            reconcile_failed_actions,
        )

        completed = (
            client.actions.get_actions_by_status(
                turn.run_id,
                status="completed",
            )
        )

        failed = (
            client.actions.get_actions_by_status(
                turn.run_id,
                status="failed",
            )
        )

        pending = (
            client.actions.get_actions_by_status(
                turn.run_id,
                status="pending",
            )
        )

        processing = (
            client.actions.get_actions_by_status(
                turn.run_id,
                status="processing",
            )
        )

        completed_names = [
            field(action, "tool_name")
            for action in completed
        ]

        print(
            "COMPLETED_ACTIONS="
            + str(len(completed))
        )
        print(
            "FAILED_ACTIONS="
            + str(len(failed))
        )
        print(
            "PENDING_ACTIONS="
            + str(len(pending))
        )
        print(
            "PROCESSING_ACTIONS="
            + str(len(processing))
        )

        print(
            "COMPLETED_TOOL_SEQUENCE="
            + json.dumps(completed_names)
        )

        if failed:
            print("FAILED_ACTION_DETAILS=")

            for action in failed:
                print(
                    json.dumps(
                        {
                            "id": field(
                                action,
                                "id",
                            ),
                            "tool_name": field(
                                action,
                                "tool_name",
                            ),
                            "tool_call_id": field(
                                action,
                                "tool_call_id",
                            ),
                            "function_args": field(
                                action,
                                "function_args",
                            ),
                        },
                        default=str,
                    )
                )

        if pending or processing:
            raise RuntimeError(
                "Run retained non-terminal Actions."
            )

        unresolved_field_ids = {
            str(
                field(
                    item,
                    "field_id",
                )
            )
            for item in unresolved
            if field(
                item,
                "field_id",
            )
        }

        reconciliation = reconcile_failed_actions(
            failed_actions=failed,
            completed_actions=completed,
            final_state=application.state.value,
            unresolved_field_ids=unresolved_field_ids,
        )

        print(
            "RECOVERED_FAILED_ACTIONS="
            + str(
                len(
                    reconciliation.recovered
                )
            )
        )
        print(
            "DEFERRED_FAILED_ACTIONS="
            + str(
                len(
                    reconciliation.deferred
                )
            )
        )
        print(
            "UNRECONCILED_FATAL_ACTIONS="
            + str(
                len(
                    reconciliation.fatal
                )
            )
        )

        if reconciliation.recovered:
            print(
                "RECOVERED_FAILED_ACTION_DETAILS="
            )

            for action in reconciliation.recovered:
                print(
                    json.dumps(
                        {
                            "id": field(
                                action,
                                "id",
                            ),
                            "tool_name": field(
                                action,
                                "tool_name",
                            ),
                            "tool_call_id": field(
                                action,
                                "tool_call_id",
                            ),
                            "function_args": field(
                                action,
                                "function_args",
                            ),
                        },
                        default=str,
                    )
                )

        if reconciliation.deferred:
            print(
                "DEFERRED_FAILED_ACTION_DETAILS="
            )

            for action in reconciliation.deferred:
                print(
                    json.dumps(
                        {
                            "id": field(
                                action,
                                "id",
                            ),
                            "tool_name": field(
                                action,
                                "tool_name",
                            ),
                            "tool_call_id": field(
                                action,
                                "tool_call_id",
                            ),
                            "function_args": field(
                                action,
                                "function_args",
                            ),
                        },
                        default=str,
                    )
                )

        if reconciliation.fatal:
            print(
                "UNRECONCILED_FATAL_ACTION_DETAILS="
            )

            for action in reconciliation.fatal:
                print(
                    json.dumps(
                        {
                            "id": field(
                                action,
                                "id",
                            ),
                            "tool_name": field(
                                action,
                                "tool_name",
                            ),
                            "tool_call_id": field(
                                action,
                                "tool_call_id",
                            ),
                            "function_args": field(
                                action,
                                "function_args",
                            ),
                        },
                        default=str,
                    )
                )

            raise RuntimeError(
                "One or more unreconciled fatal "
                "Project David Actions remain."
            )

        forbidden = [
            name
            for name in completed_names
            if name
            and (
                name.endswith(
                    "__browser_click"
                )
                or name.endswith(
                    "__browser_press_key"
                )
                or name.endswith(
                    "__browser_evaluate"
                )
            )
        ]

        if forbidden:
            raise RuntimeError(
                "Forbidden browser actions observed: "
                + repr(forbidden)
            )

        print(
            "FORBIDDEN_BROWSER_ACTIONS=0"
        )
        print(
            "APPLICATION_APPROVED="
            + (
                "YES"
                if application.state
                is ApplicationState.APPROVED
                else "NO"
            )
        )
        print(
            "REAL_APPLICATION_PREPARATION=PASS"
        )

    finally:
        ingestion_executor.close()


if __name__ == "__main__":
    main()
