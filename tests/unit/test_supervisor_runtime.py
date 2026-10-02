from types import SimpleNamespace

import pytest

import project_gideon.integrations.project_david.supervisor_runtime as runtime_module
from project_gideon.integrations.project_david.config import (
    ProjectDavidConfig,
)
from project_gideon.integrations.project_david.supervisor_session import (
    SupervisorSessionService,
)
from project_gideon.models.delegation import (
    DelegationStatus,
    JobsDelegationResult,
)
from project_gideon.models.runtime import (
    ProjectDavidRuntimeBindings,
)
from project_gideon.services.delegation import (
    JobsDelegationService,
)


class FakeJobsPort:
    def delegate_jobs(
        self,
        request,
    ):
        return JobsDelegationResult(
            status=DelegationStatus.SUCCEEDED,
            job_ids=["job-1"],
            discovered_count=1,
            ingested_count=1,
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


def test_composition_root_rejects_missing_provider_api_key(
    monkeypatch,
):
    monkeypatch.setattr(
        runtime_module,
        "resolve_provider_api_key",
        lambda: None,
    )

    bindings = ProjectDavidRuntimeBindings(
        assistant_name="gideon-supervisor",
        assistant_id="assistant-1",
        meta_data={
            "ready": True,
        },
    )

    with pytest.raises(
        RuntimeError,
        match="requires a provider API key",
    ):
        runtime_module.build_supervisor_session_service(
            client=SimpleNamespace(),
            client_factory=FakeFactory(),
            config=make_config(),
            bindings=bindings,
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


def test_composition_root_registers_jobs_delegate_when_service_supplied(
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
        jobs_service=JobsDelegationService(
            FakeJobsPort()
        ),
    )

    assert result._dispatcher.names() == (
        "jobs_delegate",
        "research_delegate",
    )



def test_composition_root_registers_application_campaign_when_service_supplied(
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

    campaign_service = SimpleNamespace()

    result = runtime_module.build_supervisor_session_service(
        client=SimpleNamespace(),
        client_factory=FakeFactory(),
        config=make_config(),
        bindings=bindings,
        campaign_service=campaign_service,
    )

    assert result._dispatcher.names() == (
        "application_campaign",
        "research_delegate",
    )


def test_composition_root_registers_jobs_and_campaign_together(
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
        jobs_service=JobsDelegationService(
            FakeJobsPort()
        ),
        campaign_service=SimpleNamespace(),
    )

    assert result._dispatcher.names() == (
        "application_campaign",
        "jobs_delegate",
        "research_delegate",
    )


def test_composition_root_does_not_fake_jobs_implementation(
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

    assert result._dispatcher.names() == (
        "research_delegate",
    )
