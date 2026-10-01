
import inspect

from project_gideon.integrations.jobs.ats_routing import (
    ATSRegistrationJobAcquisitionRouter,
)
from project_gideon.integrations.jobs.greenhouse_registration_acquisition import (
    GreenhouseRegistrationAcquisitionAdapter,
)


def test_provider_neutral_router_contains_no_greenhouse_logic():
    source = inspect.getsource(
        ATSRegistrationJobAcquisitionRouter
    ).lower()

    assert "greenhouse" not in source
    assert "boards-api" not in source
    assert "board_token" not in source


def test_router_contains_no_persistence_authority():
    source = inspect.getsource(
        ATSRegistrationJobAcquisitionRouter
    )

    assert "JobIngestionRepository" not in source
    assert "upsert_job" not in source
    assert "JobRepository" not in source


def test_greenhouse_translation_stays_in_provider_adapter():
    source = inspect.getsource(
        GreenhouseRegistrationAcquisitionAdapter
    )

    assert '"boards"' in source
    assert '"token"' in source
    assert "GREENHOUSE_SOURCE" in source


def test_provider_adapter_contains_no_ats_discovery_logic():
    source = inspect.getsource(
        GreenhouseRegistrationAcquisitionAdapter
    )

    assert "ATSDiscoveryService" not in source
    assert ".discover(target" not in source
