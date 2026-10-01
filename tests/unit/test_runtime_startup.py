from types import SimpleNamespace

import pytest

import project_gideon.__main__ as runtime


def test_main_reconciles_before_ready(
    monkeypatch,
    capsys,
):
    calls = []

    config = SimpleNamespace(
        base_url="https://project-david.example",
    )

    client = object()

    bindings = SimpleNamespace(
        assistant_id="assistant-1",
        mcp_server_id="mcp-1",
        meta_data={
            "ready": True,
            "playwright_attached_count": 9,
        },
    )

    monkeypatch.setattr(
        runtime,
        "load_project_david_config",
        lambda: (
            calls.append("config")
            or config
        ),
    )

    class FakeFactory:
        def __init__(self, supplied_config):
            assert supplied_config is config
            calls.append("factory")

        def create(self):
            calls.append("client")
            return client

    class FakeBootstrap:
        def __init__(
            self,
            *,
            client: object,
            config: object,
        ):
            assert client is globals_client
            assert config is globals_config
            calls.append("bootstrap")

        def reconcile(self):
            calls.append("reconcile")
            return bindings

    globals_client = client
    globals_config = config

    monkeypatch.setattr(
        runtime,
        "ProjectDavidClientFactory",
        FakeFactory,
    )

    monkeypatch.setattr(
        runtime,
        "ProjectDavidBootstrap",
        FakeBootstrap,
    )

    runtime.main()

    assert calls == [
        "config",
        "factory",
        "client",
        "bootstrap",
        "reconcile",
    ]

    output = capsys.readouterr().out

    assert "PROJECT_GIDEON_RUNTIME_READY" in output
    assert "assistant_id=assistant-1" in output
    assert "mcp_server_id=mcp-1" in output
    assert "playwright_tools=9" in output


def test_main_refuses_non_ready_bootstrap(
    monkeypatch,
):
    config = SimpleNamespace()

    monkeypatch.setattr(
        runtime,
        "load_project_david_config",
        lambda: config,
    )

    class FakeFactory:
        def __init__(self, supplied_config):
            assert supplied_config is config

        def create(self):
            return object()

    class FakeBootstrap:
        def __init__(
            self,
            *,
            client,
            config,
        ):
            pass

        def reconcile(self):
            return SimpleNamespace(
                assistant_id="assistant-1",
                mcp_server_id="mcp-1",
                meta_data={
                    "ready": False,
                    "playwright_attached_count": 0,
                },
            )

    monkeypatch.setattr(
        runtime,
        "ProjectDavidClientFactory",
        FakeFactory,
    )

    monkeypatch.setattr(
        runtime,
        "ProjectDavidBootstrap",
        FakeBootstrap,
    )

    with pytest.raises(
        RuntimeError,
        match="without ready state",
    ):
        runtime.main()


def test_main_propagates_bootstrap_failure(
    monkeypatch,
):
    config = SimpleNamespace()

    monkeypatch.setattr(
        runtime,
        "load_project_david_config",
        lambda: config,
    )

    class FakeFactory:
        def __init__(self, supplied_config):
            assert supplied_config is config

        def create(self):
            return object()

    class FakeBootstrap:
        def __init__(
            self,
            *,
            client,
            config,
        ):
            pass

        def reconcile(self):
            raise RuntimeError(
                "runtime unavailable"
            )

    monkeypatch.setattr(
        runtime,
        "ProjectDavidClientFactory",
        FakeFactory,
    )

    monkeypatch.setattr(
        runtime,
        "ProjectDavidBootstrap",
        FakeBootstrap,
    )

    with pytest.raises(
        RuntimeError,
        match="runtime unavailable",
    ):
        runtime.main()