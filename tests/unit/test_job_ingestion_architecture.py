import inspect

from project_gideon.ports.job_ingestion import (
    JobIngestionRepository,
)
from project_gideon.services.job_ingestion import (
    JobIngestionService,
)


def test_ingestion_repository_exposes_single_atomic_upsert_operation():
    members = [
        name
        for name, value in inspect.getmembers(
            JobIngestionRepository
        )
        if inspect.isfunction(
            value
        )
        and not name.startswith(
            "_"
        )
    ]

    assert members == [
        "upsert_job",
    ]


def test_ingestion_service_does_not_depend_on_agent_runtime():
    source = inspect.getsource(
        JobIngestionService
    ).lower()

    assert "projectdavid" not in source
    assert "toolcallrequestevent" not in source
    assert "assistant" not in source
    assert "llm" not in source


def test_ingestion_service_does_not_list_then_save():
    source = inspect.getsource(
        JobIngestionService
    )

    assert "list_for_tenant" not in source
    assert ".save(" not in source
    assert "upsert_job" in source
