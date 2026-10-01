from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(
    frozen=True,
)
class ATSPageResponse:
    requested_url: str
    final_url: str
    status_code: int
    text: str


PageGet = Callable[
    [str],
    ATSPageResponse,
]
