Project Gideon is a governed career-search and job-application system built on top of the **Project David** LLM orchestration runtime.

Gideon is not a monolithic “job application agent.” It is a set of deterministic domain services, bounded agent-facing tools, specialist factions, durable state machines, and browser capabilities coordinated by a career supervisor running through Project David.

The core design principle is simple:

> **LLMs decide what to ask for; deterministic services decide what is allowed to happen.**

Candidate facts, canonical job records, application state, browser authority, approval state, and submission permissions remain outside the language model.

---

## Goals

Gideon is designed to:

- discover real jobs from external recruiting systems;
- canonicalise and deduplicate jobs before semantic reasoning;
- compare authoritative job records against candidate evidence;
- create durable application campaigns;
- prepare application forms without inventing answers;
- surface unknown or ambiguous questions instead of guessing;
- require explicit human approval before external submission;
- preserve a complete, inspectable application lifecycle independently of any single LLM run.

The system is intentionally split into **agentic reasoning** and **deterministic execution**.

---

## High-level architecture

```text
                                      PROJECT GIDEON
====================================================================================================

                                        Human / Client
                                             |
                                             v
                                +--------------------------+
                                |   Gideon Supervisor      |
                                |  Project David Assistant |
                                +------------+-------------+
                                             |
                          reasoning / semantic selection
                                             |
             +-------------------------------+--------------------------------+
             |                               |                                |
             v                               v                                v
   +--------------------+          +-------------------+          +------------------------+
   |  Consumer Tools    |          | Project David     |          | Specialist Delegation  |
   |  Gideon-owned      |          | Native Tools      |          | / Factions             |
   +---------+----------+          +---------+---------+          +-----------+------------+
             |                               |                                |
             |                               |                                |
       +-----+---------+                 file_search                     research_delegate
       |               |                     |                          jobs_delegate
       v               v                     v                                |
  job_lookup   application_campaign   Candidate Knowledge                     |
       |               |              / Vector Store                         |
       |               |                     |                                |
       |               |                     v                                v
       |               |             authoritative CV                +---------------------+
       |               |             skills / experience             |    Jobs Faction      |
       |               |                                              +----------+----------+
       |               |                                                         |
       |               |                                        ATS resolution / acquisition
       |               |                                                         |
       |               |                                 Greenhouse / future ATS adapters
       |               |                                                         |
       |               |                                                         v
       |               |                                               canonical ingestion
       |               |                                               + deduplication
       |               |                                                         |
       v               |                                                         v
+------------------+   |                                                +------------------+
| Canonical Job    |<--+------------------------------------------------| Job Repository   |
| Reader           |                                                    +------------------+
+--------+---------+
         |
         | authoritative job evidence
         v
+------------------------------------------------------------------------------------------+
|                            SEMANTIC FIT DECISION                                         |
|             Canonical job evidence  <->  Candidate file_search evidence                 |
+-------------------------------------------+----------------------------------------------+
                                            |
                                            v
                                  selected canonical job
                                            |
                                            v
                                +--------------------------+
                                | application_campaign     |
                                | shortlist                |
                                | start_preparation        |
                                +------------+-------------+
                                             |
                                             v
                                +--------------------------+
                                | Durable JobApplication   |
                                | Application Repository   |
                                +------------+-------------+
                                             |
                                             v
                                +--------------------------+
                                | Application Lifecycle    |
                                | deterministic state      |
                                | transition authority     |
                                +------------+-------------+
                                             |
                                             v
                                  PREPARING / FORM WORKFLOW
                                             |
                                             v
                                +--------------------------+
                                | ApplicationPreparation   |
                                | Service                  |
                                +------------+-------------+
                                             |
                                             v
                                +--------------------------+
                                | Governed Playwright MCP  |
                                | capability allow-list    |
                                +------------+-------------+
                                             |
                               fill / inspect / upload only
                                             |
                       +---------------------+---------------------+
                       |                                           |
                       v                                           v
                 NEEDS_INPUT                                READY_FOR_REVIEW
                       |                                           |
                       | human supplies data                        |
                       +---------------------+                     |
                                             |                     v
                                             |          +-----------------------+
                                             |          | Explicit User Approval|
                                             |          | ApprovalService       |
                                             |          +-----------+-----------+
                                             |                      |
                                             +--------------------->|
                                                                    v
                                                               APPROVED
                                                                    |
                                                                    v
                                                         +----------------------+
                                                         | Submission Guard     |
                                                         | consequential action |
                                                         | boundary             |
                                                         +----------+-----------+
                                                                    |
                                                                    v
                                                               SUBMITTED

====================================================================================================
```

---

## Architectural principles

### 1. The supervisor does not own durable truth

The Gideon supervisor coordinates work, but authoritative state is held elsewhere.

The supervisor may decide that a job should be shortlisted, that more evidence is needed, or that preparation should begin. It does **not** directly own:

- candidate truth;
- canonical job truth;
- application lifecycle state;
- browser permissions;
- approval state;
- submission authority.

A supervisor run may disappear without destroying the application campaign.

---

### 2. Canonicalise before reasoning

Jobs are normalised and deduplicated before LLM-based fit analysis.

Logical flow:

```text
external job source
      |
      v
discover
      |
      v
normalise
      |
      v
canonical identity / dedupe
      |
      v
durable Job record
      |
      v
semantic fit analysis
```

This prevents the model from repeatedly reasoning over duplicate, stale, or source-specific representations of the same job.

Canonical IDs are source-stable identities such as:

```text
greenhouse:<employer>:<source_job_id>
```

The exact source implementation is deliberately hidden behind Gideon’s job acquisition and repository boundaries.

---

### 3. Candidate evidence comes from the configured knowledge store

The supervisor must not invent candidate experience.

For fit analysis, Gideon uses Project David’s native `file_search` against the candidate knowledge store.

The configured CV and candidate documents are treated as evidence. The model may reason over retrieved evidence, but absence of evidence is not permission to fabricate a claim.

```text
Candidate Profile
      +
Candidate Knowledge Store
      |
      v
Project David native file_search
      |
      v
retrieved evidence
      |
      v
semantic comparison
```

The structured `CandidateProfile` contains reusable canonical information such as identity, preferences, work authorisation and default CV references.

Job-specific generated claims do not belong in the canonical candidate profile.

---

## Supervisor tool model

Gideon deliberately distinguishes **Project David native tools** from **Gideon consumer tools**.

### Native Project David tools

Native tools execute inside the Project David runtime.

Current important example:

```text
file_search
```

`file_search` is used to retrieve candidate evidence from the assistant’s configured vector store.

Native tool activity belongs to Project David’s persisted Action lifecycle and is **not** equivalent to Gideon’s consumer-tool presentation stream.

---

### Gideon consumer tools

Consumer tools cross the boundary from the Project David assistant into Gideon-owned services.

Current supervisor-facing tools include:

| Tool | Responsibility |
|---|---|
| `jobs_delegate` | Delegate discovery, ingestion and canonical job reconciliation to the jobs faction |
| `job_lookup` | Read authoritative canonical job details by ID |
| `application_campaign` | Mutate durable campaign state through controlled actions such as `shortlist` and `start_preparation` |
| `research_delegate` | Delegate substantial external research to the research faction |

Consumer-tool handlers validate typed Pydantic requests before invoking Gideon services.

Project David remains responsible for the run/action/tool-message lifecycle and Turn-N continuation.

---

## Project David integration

Project David provides Gideon’s LLM runtime and orchestration substrate.

Gideon uses Project David for:

- assistant identity and reconciliation;
- threads, messages and runs;
- model inference;
- native tools such as `file_search`;
- consumer-tool call events;
- Action persistence;
- MCP registration and discovery;
- durable MCP attachment;
- governed browser capability exposure.

Startup follows the pattern:

```python
config = load_project_david_config()

client = ProjectDavidClientFactory(
    config
).create()

bindings = ProjectDavidBootstrap(
    client=client,
    config=config,
).reconcile()
```

Runtime IDs are reconciled resources, not static configuration.

A healthy Gideon startup requires the Project David composition to be ready before agent execution begins.

---

## Bootstrap and runtime reconciliation

`ProjectDavidBootstrap` reconciles the runtime rather than assuming that external resources already exist in a correct state.

Readiness includes:

```text
logical Gideon supervisor
        |
        +--> assistant exists / reconciled
        |
        +--> candidate file_search vector store attached
        |
        +--> Playwright MCP server registration exists
        |
        +--> MCP discovery succeeds
        |
        +--> discovered capabilities satisfy Gideon's policy
        |
        +--> governed capabilities are durably attached
        |
        `--> runtime bindings marked ready
```

Project David deployment and network topology remain outside Gideon’s domain responsibility.

---

## Jobs faction

Job acquisition is isolated from career-supervisor reasoning.

The supervisor does not guess ATS implementation details. It provides typed employer intent and delegates discovery to the jobs faction.

The jobs faction owns:

- employer/source resolution;
- ATS detection;
- acquisition;
- ingestion;
- normalisation;
- canonical identity;
- deduplication;
- authoritative `Job` persistence.

A simplified flow:

```text
Supervisor
   |
   | jobs_delegate
   v
JobsDelegationService
   |
   v
Jobs Delegation Port
   |
   v
ATS Acquisition Router
   |
   +--> Greenhouse detector / registration
   |
   +--> Greenhouse acquisition adapter
   |
   `--> future ATS adapters
            |
            v
     ingestion executor
            |
            v
     canonical Job repository
```

The jobs faction returns canonical job identifiers to the supervisor.

The supervisor then uses `job_lookup` when it needs authoritative details for fit analysis or application preparation.

It must not infer requirements from an identifier alone.

---

## Semantic job selection

Semantic selection combines two authoritative evidence planes:

```text
                    +------------------------+
                    | Canonical Job Records  |
                    | via job_lookup         |
                    +-----------+------------+
                                |
                                |
                                v
                     +-----------------------+
                     | semantic comparison   |
                     +-----------------------+
                                ^
                                |
                                |
                    +-----------+------------+
                    | Candidate CV Evidence  |
                    | native file_search     |
                    +------------------------+
```

The model performs the semantic judgement.

The model does **not** get authority to mutate durable state simply because it selected a job.

Mutation happens through `application_campaign`.

---

## Application campaigns

Discovery does not automatically create applications.

A durable campaign begins only when a canonical job is shortlisted for a candidate.

`ApplicationCampaignService` owns this boundary.

Current supervisor actions:

### `shortlist`

Inputs:

```text
tenant_id
job_id
candidate_id
```

The service:

1. verifies that the canonical job exists;
2. verifies that the candidate exists;
3. ensures that the tenant/job/candidate tuple does not create duplicate campaigns;
4. creates or reuses a durable `JobApplication`;
5. transitions it to `SHORTLISTED`.

### `start_preparation`

Input:

```text
tenant_id
application_id
```

The service only permits preparation from a valid shortlisted campaign and transitions the application to `PREPARING`.

---

## Durable application lifecycle

`ApplicationLifecycleService` is the deterministic authority for application-state transitions.

Agents can **request** a transition.

Agents do not define what transitions are legal.

```text
DISCOVERED
    |
    v
SHORTLISTED
    |
    v
PREPARING
    |
    v
FORM_IN_PROGRESS
   / \
  /   \
 v     v
NEEDS_INPUT ------------------+
  |                           |
  +----------+----------------+
             |
             v
      READY_FOR_REVIEW
             |
             | explicit approval
             v
         APPROVED
             |
             v
        SUBMITTED
             |
        +----+----+
        |         |
        v         v
   WITHDRAWN    CLOSED
        |
        v
      CLOSED
```

Failure and recovery paths also exist:

```text
PREPARING --------> FAILED
FORM_IN_PROGRESS -> FAILED

FAILED -> PREPARING
FAILED -> FORM_IN_PROGRESS
FAILED -> CLOSED
```

The complete application model also tracks browser session identity, selected CV/cover-letter files, unresolved questions, timestamps and metadata.

---

## Application preparation

`ApplicationPreparationService` owns deterministic form preparation.

Responsibilities include:

- validating package/application identity;
- creating or resuming a browser session;
- inspecting normalised browser controls;
- filling only authoritative known values;
- uploading the selected CV where the target control can be identified safely;
- surfacing unknown required questions;
- transitioning to `NEEDS_INPUT` or `READY_FOR_REVIEW`.

The preparation service has **no submission capability**.

That separation is intentional.

---

## Governed browser authority

Gideon treats browser interaction as a capability-security problem.

The preparation path does not receive generic browser authority.

In particular, generic `CLICK` is intentionally excluded from preparation-time capability because an arbitrary click could activate a consequential control such as **Submit**.

```text
Project David MCP discovery
          |
          v
available Playwright tools
          |
          v
Gideon MCP capability policy
          |
          v
preparation-safe subset only
          |
          v
durable assistant attachment
```

Browser actions are checked against the preparation allow-list before execution.

The goal is not merely to prompt the model “do not submit.”

The model is structurally denied the capability required to submit during preparation.

---

## Human approval and submission boundary

External submission is a consequential action and therefore sits behind an explicit human approval boundary.

The intended control path is:

```text
READY_FOR_REVIEW
       |
       v
ApprovalRequest
       |
       v
explicit user decision
       |
       v
APPROVED
       |
       v
SubmissionGuard
       |
       v
submission-capable execution path
       |
       v
SUBMITTED
```

Unknown or ambiguous application answers are surfaced to the user rather than silently invented.

Approval is durable domain state, not merely a conversational “yes” interpreted by the LLM.

---

## Data ownership

Gideon uses tenant-scoped domain records.

Core durable entities include:

```text
CandidateProfile
Job
JobApplication
ApprovalRequest
```

Repositories are accessed through ports so domain services are not coupled to a particular persistence implementation.

The repository layer currently includes in-memory implementations suitable for deterministic tests and composition work.

Persistence can be replaced without changing the application lifecycle or supervisor contract.

---

## Logical responsibility boundaries

```text
+----------------------+---------------------------------------------------------+
| Component            | Owns                                                    |
+----------------------+---------------------------------------------------------+
| Project David        | inference, runs, actions, native tools, MCP, tool events |
| Gideon Supervisor    | coordination and semantic reasoning                     |
| Jobs Faction         | acquisition, ingestion, canonical job state             |
| Research Faction     | delegated external research orchestration               |
| Candidate Store      | authoritative candidate evidence                        |
| Job Repository       | authoritative canonical jobs                            |
| Campaign Service     | creation/start of durable application campaigns         |
| Lifecycle Service    | legal application state transitions                     |
| Preparation Service  | safe deterministic form preparation                     |
| Playwright Policy    | preparation-time browser capability boundary            |
| Approval Service     | explicit durable approval                               |
| Submission Guard     | final consequential-action boundary                     |
+----------------------+---------------------------------------------------------+
```

---

## Repository structure

The project is organised around domain models, service boundaries, ports, repositories and integrations.

```text
project-gideon/
|
+-- scripts/
|   `-- live_jobs_delegate_e2e.py
|
+-- src/project_gideon/
|   |
|   +-- __main__.py
|   |
|   +-- models/
|   |   +-- application.py
|   |   +-- application_campaign.py
|   |   +-- application_package.py
|   |   +-- approval.py
|   |   +-- browser.py
|   |   +-- candidate.py
|   |   +-- job.py
|   |   +-- job_lookup.py
|   |   +-- preparation.py
|   |   +-- runtime.py
|   |   `-- session.py
|   |
|   +-- services/
|   |   +-- application_campaign.py
|   |   +-- application_lifecycle.py
|   |   +-- application_preparation.py
|   |   +-- approval.py
|   |   +-- delegation.py
|   |   `-- submission_guard.py
|   |
|   +-- ports/
|   |   +-- delegation.py
|   |   +-- playwright.py
|   |   `-- repositories.py
|   |
|   +-- repositories/
|   |   `-- memory.py
|   |
|   +-- integrations/
|       |
|       +-- jobs/
|       |   +-- async_ingestion.py
|       |   +-- ats_routing.py
|       |   +-- delegation.py
|       |   +-- greenhouse.py
|       |   +-- greenhouse_discovery.py
|       |   `-- greenhouse_registration_acquisition.py
|       |
|       +-- playwright/
|       |   `-- capabilities.py
|       |
|       `-- project_david/
|           +-- assistants.py
|           +-- bootstrap.py
|           +-- client.py
|           +-- config.py
|           +-- mcp_policy.py
|           +-- mcp_registry.py
|           +-- research.py
|           +-- supervisor_runtime.py
|           +-- supervisor_session.py
|           `-- consumer_tools/
|               +-- application_campaign.py
|               +-- dispatcher.py
|               +-- job_lookup.py
|               +-- jobs.py
|               `-- research.py
|
`-- tests/
    `-- unit/
```

The exact tree will evolve; the architectural boundaries are more important than individual filenames.

---

## Configuration

Gideon’s canonical Project David runtime settings are:

```text
PROJECTDAVID_BASE_URL
PROJECTDAVID_API_KEY
GIDEON_ASSISTANT_MODEL
PLAYWRIGHT_MCP_URL
```

Development aliases are supported by the current configuration loader, including:

```text
BASE_URL
PROJECT_DAVID_PLATFORM_BASE_URL
ENTITIES_BASE_URL

DEV_PROJECT_DAVID_CORE_TEST_USER_KEY

MCP_TEST_MODEL_ID
```

Provider inference credentials are resolved independently of the Project David user API key.

Supported provider credential names currently include:

```text
GIDEON_PROVIDER_API_KEY
TOGETHER_API_KEY
HYPERBOLIC_API_KEY
OPENAI_API_KEY
```

The Project David API key authenticates Gideon **to Project David**.

The provider API key authorises **upstream model inference**.

These are separate security domains.

---

## Current proven live flow

The current live semantic E2E proves:

```text
real Stripe discovery
        |
        v
ATS source resolution
        |
        v
canonical ingestion + dedupe
        |
        v
bounded canonical evaluation set
        |
        +--> native file_search -> candidate CV evidence
        |
        +--> job_lookup -> authoritative Job evidence
        |
        v
semantic CV <-> job comparison
        |
        v
selected canonical job
        |
        v
application_campaign.shortlist
        |
        v
durable JobApplication
        |
        v
application_campaign.start_preparation
        |
        v
PREPARING
```

The tested live path intentionally does **not** perform browser automation or external submission.

The wider domain architecture contains the guarded preparation, approval and submission lifecycle, but those later stages should be considered separate acceptance boundaries until exercised by their own live E2E.

---

## Testing strategy

Gideon is tested as a system of contracts rather than only as prompt behaviour.

The project uses:

- unit tests for deterministic domain services;
- typed request/response contract tests;
- lifecycle transition tests;
- repository/deduplication tests;
- supervisor consumer-tool tests;
- Project David runtime composition tests;
- native-tool persistence checks;
- live external job-discovery E2E;
- bounded semantic trajectory E2E.

The live semantic test verifies both reasoning and durable effects.

A successful run proves that the supervisor:

1. delegates real job discovery;
2. operates on canonical jobs;
3. retrieves authoritative candidate evidence through native `file_search`;
4. reads authoritative job details through `job_lookup`;
5. performs semantic comparison;
6. selects a job from a bounded set;
7. creates exactly one durable application campaign;
8. starts preparation;
9. leaves the application in authoritative `PREPARING` state.

At the time this architecture document was written, the unit suite contained:

```text
192 passing tests
```

---

## Evaluation philosophy

Gideon’s useful metric is not “did the model produce convincing prose?”

The important question is whether the system can complete a qualified application workflow safely and correctly.

The architecture therefore favours:

```text
deterministic contracts
        +
semantic decisions
        +
tool trajectory
        +
fault injection
        +
real external E2E
```

A useful top-level system metric is:

> **Qualified Application Completion Rate**

Real failures should become deterministic regression fixtures wherever possible.

---

## Safety model

Gideon follows several hard rules:

1. **Do not invent candidate facts.**
2. **Do not infer job requirements from IDs alone.**
3. **Do not allow discovery to mutate application state implicitly.**
4. **Do not allow the model to define lifecycle transitions.**
5. **Do not silently answer unknown required form questions.**
6. **Do not expose generic consequential browser authority during preparation.**
7. **Do not submit externally without explicit human approval.**

These constraints are implemented in code and service boundaries rather than relying exclusively on system prompts.

---

## Design summary

Project Gideon is best understood as a **career-domain control plane around an LLM supervisor**.

Project David provides the sovereign orchestration runtime.

Gideon provides the career-domain authority.

```text
LLM / Supervisor
      |
      | proposes and coordinates
      v
Typed Gideon Boundaries
      |
      | validate
      v
Deterministic Domain Services
      |
      | enforce
      v
Durable State + Governed Capabilities
      |
      | only then
      v
External Side Effects
```

That separation is the architecture.

The LLM is powerful enough to reason across imperfect job descriptions and candidate evidence, but it is deliberately **not** powerful enough to redefine truth, lifecycle rules, approval, or submission authority.
'''

path = Path("/mnt/data/README.md")
path.write_text(readme, encoding="utf-8")
print(f"Created {path} ({path.stat().st_size} bytes)")
