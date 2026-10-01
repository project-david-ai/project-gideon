
import inspect

from project_gideon.integrations.jobs.greenhouse import (
    GreenhouseJobAcquisitionPort,
)


def test_greenhouse_adapter_is_acquisition_only():
    source = inspect.getsource(
        GreenhouseJobAcquisitionPort
    )

    assert "JobRepository" not in source
    assert "JobIngestionRepository" not in source
    assert "upsert_job" not in source
    assert ".save(" not in source


def test_greenhouse_adapter_does_not_decide_duplicates():
    source = inspect.getsource(
        GreenhouseJobAcquisitionPort
    )

    assert "canonical_job_fingerprint" not in source
    assert "JobMatchType" not in source


def test_greenhouse_adapter_does_not_use_browser_automation():
    source = inspect.getsource(
        GreenhouseJobAcquisitionPort
    ).lower()

    assert "playwright" not in source
    assert "selenium" not in source
    assert "browser_" not in source


def test_greenhouse_adapter_uses_public_structured_endpoint():
    source = inspect.getsource(
        GreenhouseJobAcquisitionPort
    )

    assert "GREENHOUSE_API_ROOT" in source
    assert "content=true" in source
