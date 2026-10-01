
from __future__ import annotations

import html
import json
from collections.abc import Callable
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from project_gideon.models.delegation import (
    JobsDelegationRequest,
)
from project_gideon.models.job import (
    Job,
)
from project_gideon.models.job_ingestion import (
    JobIngestionCandidate,
)


GREENHOUSE_SOURCE = "greenhouse"

GREENHOUSE_API_ROOT = (
    "https://boards-api.greenhouse.io/v1/boards"
)


class GreenhouseSourceError(RuntimeError):
    pass


class GreenhouseBoardTarget(BaseModel):
    """
    One employer-owned Greenhouse public job board.
    """

    token: str
    company: str | None = None


class GreenhouseAcquisitionParameters(BaseModel):
    """
    Source-specific parameters carried inside JobsDelegationRequest.parameters.
    """

    boards: list[GreenhouseBoardTarget] = Field(
        min_length=1
    )

    max_jobs_per_board: int | None = Field(
        default=None,
        ge=1,
    )


class GreenhouseNamedResource(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )

    id: int | str | None = None
    name: str


class GreenhouseLocation(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )

    name: str | None = None


class GreenhouseJobPayload(BaseModel):
    """
    Validated subset of Greenhouse's public Job Board response.

    Extra source fields are accepted so Greenhouse can evolve the payload
    without breaking Gideon's adapter.
    """

    model_config = ConfigDict(
        extra="allow"
    )

    id: int | str
    title: str

    absolute_url: str
    content: str | None = None

    company_name: str | None = None
    requisition_id: str | int | None = None
    internal_job_id: str | int | None = None

    location: GreenhouseLocation | None = None

    departments: list[GreenhouseNamedResource] = Field(
        default_factory=list
    )

    offices: list[GreenhouseNamedResource] = Field(
        default_factory=list
    )

    first_published: str | None = None
    updated_at: str | None = None

    metadata: list[dict[str, Any]] | None = None


class GreenhouseJobsResponse(BaseModel):
    model_config = ConfigDict(
        extra="allow"
    )

    jobs: list[GreenhouseJobPayload] = Field(
        default_factory=list
    )


JsonGet = Callable[
    [str],
    dict[str, Any],
]


class _TextExtractor(HTMLParser):
    def __init__(
        self,
    ) -> None:
        super().__init__(
            convert_charrefs=True
        )

        self._parts: list[str] = []

    def handle_data(
        self,
        data: str,
    ) -> None:
        text = data.strip()

        if text:
            self._parts.append(
                text
            )

    def text(
        self,
    ) -> str:
        return " ".join(
            self._parts
        )


def greenhouse_html_to_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    parser = _TextExtractor()

    parser.feed(
        html.unescape(
            value
        )
    )

    parser.close()

    return parser.text()


def default_greenhouse_json_get(
    url: str,
) -> dict[str, Any]:
    """
    Minimal dependency-free HTTPS transport for Greenhouse public reads.
    """

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Project-Gideon/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            payload = response.read()
    except Exception as exc:
        raise GreenhouseSourceError(
            f"Greenhouse request failed: {exc}"
        ) from exc

    try:
        decoded = json.loads(
            payload.decode(
                "utf-8"
            )
        )
    except Exception as exc:
        raise GreenhouseSourceError(
            "Greenhouse returned invalid JSON."
        ) from exc

    if not isinstance(
        decoded,
        dict,
    ):
        raise GreenhouseSourceError(
            "Greenhouse response root must be an object."
        )

    return decoded


class GreenhouseJobAcquisitionPort:
    """
    Structured acquisition adapter for employer-owned Greenhouse boards.

    This adapter fetches and normalises public source data only.
    Canonical duplicate authority and persistence remain in Gideon's
    authoritative ingestion layer.
    """

    def __init__(
        self,
        *,
        json_get: JsonGet = default_greenhouse_json_get,
    ) -> None:
        self._json_get = json_get

    def _build_url(
        self,
        token: str,
    ) -> str:
        clean_token = token.strip()

        if not clean_token:
            raise ValueError(
                "Greenhouse board token cannot be empty."
            )

        return (
            f"{GREENHOUSE_API_ROOT}/"
            f"{quote(clean_token, safe='')}"
            "/jobs?content=true"
        )

    def _load_parameters(
        self,
        request: JobsDelegationRequest,
    ) -> GreenhouseAcquisitionParameters:
        if (
            request.source is not None
            and request.source.lower()
            not in {
                GREENHOUSE_SOURCE,
                "employer_ats",
            }
        ):
            raise ValueError(
                "Greenhouse adapter cannot service "
                f"source={request.source!r}."
            )

        return GreenhouseAcquisitionParameters.model_validate(
            request.parameters
        )

    def _normalise_job(
        self,
        *,
        request: JobsDelegationRequest,
        board: GreenhouseBoardTarget,
        payload: GreenhouseJobPayload,
    ) -> JobIngestionCandidate:
        source_job_id = str(
            payload.id
        )

        company = (
            payload.company_name
            or board.company
            or board.token
        )

        requisition_id = (
            str(
                payload.requisition_id
            )
            if payload.requisition_id is not None
            else None
        )

        job = Job(
            id=(
                f"greenhouse:"
                f"{board.token}:"
                f"{source_job_id}"
            ),
            tenant_id=request.tenant_id,
            source=GREENHOUSE_SOURCE,
            source_job_id=source_job_id,
            source_url=payload.absolute_url,
            application_url=payload.absolute_url,
            title=payload.title,
            company=company,
            description=greenhouse_html_to_text(
                payload.content
            ),
            location=(
                payload.location.name
                if payload.location
                else None
            ),
            requirements=[],
            meta_data={
                "source_type": "employer_ats",
                "ats": GREENHOUSE_SOURCE,
                "board_token": board.token,
                "internal_job_id": (
                    str(
                        payload.internal_job_id
                    )
                    if payload.internal_job_id is not None
                    else None
                ),
                "first_published": payload.first_published,
                "updated_at": payload.updated_at,
                "departments": [
                    department.name
                    for department in payload.departments
                ],
                "offices": [
                    office.name
                    for office in payload.offices
                ],
                "metadata": payload.metadata or [],
            },
        )

        return JobIngestionCandidate(
            job=job,
            requisition_id=requisition_id,
        )

    def _fetch(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        parameters = self._load_parameters(
            request
        )

        candidates: list[
            JobIngestionCandidate
        ] = []

        for board in parameters.boards:
            raw = self._json_get(
                self._build_url(
                    board.token
                )
            )

            response = GreenhouseJobsResponse.model_validate(
                raw
            )

            jobs = response.jobs

            if (
                parameters.max_jobs_per_board
                is not None
            ):
                jobs = jobs[
                    : parameters.max_jobs_per_board
                ]

            for payload in jobs:
                candidates.append(
                    self._normalise_job(
                        request=request,
                        board=board,
                        payload=payload,
                    )
                )

        return candidates

    def discover(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._fetch(
            request
        )

    def ingest(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._fetch(
            request
        )

    def refresh(
        self,
        request: JobsDelegationRequest,
    ) -> list[JobIngestionCandidate]:
        return self._fetch(
            request
        )
