from __future__ import annotations

from collections.abc import Callable


from project_gideon.integrations.project_david.client import (
    ProjectDavidClientFactory,
)
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.consumer_tools.dispatcher import (
    ConsumerToolDispatcher,
)
from project_gideon.integrations.project_david.consumer_tools.jobs import (
    JOBS_DELEGATE_TOOL_NAME,
    create_jobs_delegate_handler,
)
from project_gideon.integrations.project_david.consumer_tools.research import (
    RESEARCH_DELEGATE_TOOL_NAME,
    create_research_delegate_handler,
)
from project_gideon.integrations.project_david.research import (
    ProjectDavidResearchDelegationPort,
    resolve_provider_api_key,
)
from project_gideon.integrations.project_david.supervisor_session import (
    SupervisorSessionService,
)
from project_gideon.models.presentation import (
    GideonPresentationEvent,
)
from project_gideon.models.runtime import (
    ProjectDavidRuntimeBindings,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
    ResearchDelegationService,
)


def build_supervisor_session_service(
    *,
    client,
    client_factory: ProjectDavidClientFactory,
    config: ProjectDavidConfig,
    bindings: ProjectDavidRuntimeBindings,
    jobs_service: JobsDelegationService | None = None,
    presentation_sink: Callable[
        [GideonPresentationEvent],
        None,
    ]
    | None = None,
) -> SupervisorSessionService:
    """
    Compose Gideon's career-supervisor execution surface.

    Cross-faction tools are registered here. The session loop remains generic.
    """

    if not bindings.meta_data.get(
        "ready",
        False,
    ):
        raise RuntimeError(
            "Cannot create supervisor session service from non-ready "
            "Project David bindings."
        )

    research_port = ProjectDavidResearchDelegationPort(
        client_factory=client_factory.create_research_client,
        model=config.assistant_model,
        provider_api_key=resolve_provider_api_key(),
    )

    research_port.bind_presentation(
        presentation_sink=presentation_sink,
    )

    research_service = ResearchDelegationService(
        research_port
    )

    dispatcher = ConsumerToolDispatcher()

    dispatcher.register(
        RESEARCH_DELEGATE_TOOL_NAME,
        create_research_delegate_handler(
            research_service
        ),
    )

    if jobs_service is not None:
        jobs_service.bind_presentation(
            presentation_sink=presentation_sink,
        )

        dispatcher.register(
            JOBS_DELEGATE_TOOL_NAME,
            create_jobs_delegate_handler(
                jobs_service
            ),
        )

    return SupervisorSessionService(
        client=client,
        assistant_id=bindings.assistant_id,
        model=config.assistant_model,
        dispatcher=dispatcher,
        provider_api_key=resolve_provider_api_key(),
        presentation_sink=presentation_sink,
    )
