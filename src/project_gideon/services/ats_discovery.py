
from __future__ import annotations

from collections.abc import Sequence

from project_gideon.models.ats_discovery import (
    ATSDiscoveryResult,
    ATSDiscoveryStatus,
    EmployerTarget,
)
from project_gideon.ports.ats_discovery import (
    ATSDetectorPort,
)


class ATSDiscoveryService:
    """
    Provider-neutral deterministic ATS discovery orchestrator.

    Provider-specific detection remains behind ATSDetectorPort.
    """

    def __init__(
        self,
        detectors: Sequence[
            ATSDetectorPort
        ],
    ) -> None:
        self._detectors = tuple(
            detectors
        )

    def discover(
        self,
        target: EmployerTarget,
    ) -> ATSDiscoveryResult:
        for detector in self._detectors:
            registration = detector.detect(
                target
            )

            if registration is not None:
                return ATSDiscoveryResult(
                    status=ATSDiscoveryStatus.FOUND,
                    target=target,
                    registration=registration,
                )

        return ATSDiscoveryResult(
            status=ATSDiscoveryStatus.NOT_FOUND,
            target=target,
        )
