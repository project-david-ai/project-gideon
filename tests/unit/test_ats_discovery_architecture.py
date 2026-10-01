
import inspect

from project_gideon.integrations.jobs.greenhouse_discovery import (
    GreenhouseATSDetector,
)
from project_gideon.services.ats_discovery import (
    ATSDiscoveryService,
)


def test_provider_neutral_service_has_no_greenhouse_logic():
    source = inspect.getsource(
        ATSDiscoveryService
    ).lower()

    assert "greenhouse" not in source
    assert "boards-api" not in source


def test_greenhouse_detector_has_no_browser_or_agent_dependency():
    source = inspect.getsource(
        GreenhouseATSDetector
    ).lower()

    assert "playwright" not in source
    assert "selenium" not in source
    assert "assistant" not in source
    assert "llm" not in source


def test_detector_has_no_canonical_job_persistence_authority():
    source = inspect.getsource(
        GreenhouseATSDetector
    )

    assert "JobIngestionRepository" not in source
    assert "upsert_job" not in source
    assert "JobRepository" not in source


def test_greenhouse_registration_requires_api_verification():
    source = inspect.getsource(
        GreenhouseATSDetector
    )

    assert "GreenhouseJobsResponse.model_validate" in source
