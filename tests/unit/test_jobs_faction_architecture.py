
import inspect

from project_gideon.integrations.jobs.async_ingestion import (
    ThreadedJobIngestionExecutor,
)
from project_gideon.integrations.jobs.delegation import (
    GideonJobsDelegationPort,
)


def test_jobs_delegation_port_contains_no_event_loop_management():
    source = inspect.getsource(
        GideonJobsDelegationPort
    )

    assert "asyncio" not in source
    assert "run_coroutine_threadsafe" not in source
    assert "new_event_loop" not in source
    assert "asyncio.run" not in source


def test_jobs_delegation_port_does_not_decide_duplicate_identity():
    source = inspect.getsource(
        GideonJobsDelegationPort
    )

    assert "canonical_job_fingerprint" not in source
    assert "source_job_id ==" not in source
    assert "requisition_id ==" not in source


def test_async_bridge_uses_long_lived_event_loop_not_asyncio_run():
    source = inspect.getsource(
        ThreadedJobIngestionExecutor
    )

    assert "new_event_loop" in source
    assert "run_forever" in source
    assert "run_coroutine_threadsafe" in source

    forbidden = "asyncio" + ".run("

    assert forbidden not in source


def test_jobs_faction_uses_authoritative_ingestion_result_for_counts():
    source = inspect.getsource(
        GideonJobsDelegationPort
    )

    assert "result.created" in source
    assert "duplicate_count" in source
    assert "ingested_count" in source
