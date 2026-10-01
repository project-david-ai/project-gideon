from types import SimpleNamespace

import pytest

import project_gideon.integrations.project_david.supervisor_runtime as runtime_module
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.supervisor_session import (
    SupervisorSessionService,
)
from project_gideon.models.runtime import (
    ProjectDavidRuntimeBindings,
)


class FakeFactory:
    def create_research_client(
        self,
    ):
        return SimpleNamespace()


def make_config():
    return ProjectDavidConfig(
        base_url="https://project-david.example",
        api_key="test-key",
        assistant_name="gideon-supervisor",
        assistant_model="test-model",
        playwright_mcp_name="playwright-primary",
        playwright_mcp_url="https://playwright.example/mcp",
    )


def test_composition_root_builds_ready_supervisor_session(
    monkeypatch,
):
    monkeypatch.setattr(
        runtime_module,
        "resolve_provider_api_key",
        lambda: "provider-key",
    )

    bindings = ProjectDavidRuntimeBindings(
        assistant_name="gideon-supervisor",
        assistant_id="assistant-1",
        meta_data={
            "ready": True,
        },
    )

    result = runtime_module.build_supervisor_session_service(
        client=SimpleNamespace(),
        client_factory=FakeFactory(),
        config=make_config(),
        bindings=bindings,
    )

    assert isinstance(
        result,
        SupervisorSessionService,
    )

    assert result._assistant_id == "assistant-1"
    assert result._model == "test-model"

    assert result._dispatcher.names() == (
        "research_delegate",
    )


def test_composition_root_rejects_non_ready_bindings():
    bindings = ProjectDavidRuntimeBindings(
        assistant_name="gideon-supervisor",
        assistant_id="assistant-1",
        meta_data={
            "ready": False,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="non-ready",
    ):
        runtime_module.build_supervisor_session_service(
            client=SimpleNamespace(),
            client_factory=FakeFactory(),
            config=make_config(),
            bindings=bindings,
        )
