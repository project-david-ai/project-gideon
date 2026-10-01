
from __future__ import annotations

from typing import Protocol

from project_gideon.models.ats_discovery import (
    ATSRegistration,
    EmployerTarget,
)


class ATSDetectorPort(
    Protocol,
):
    """
    One deterministic provider detector.

    A detector either returns a verified provider registration or None.
    """

    def detect(
        self,
        target: EmployerTarget,
    ) -> ATSRegistration | None:
        ...
