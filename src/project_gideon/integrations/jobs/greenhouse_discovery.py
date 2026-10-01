
from __future__ import annotations

import re
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import (
    urljoin,
    urlparse,
)
from urllib.request import (
    Request,
    urlopen,
)

from project_gideon.integrations.jobs.greenhouse import (
    GREENHOUSE_API_ROOT,
    GreenhouseJobsResponse,
)
from project_gideon.integrations.jobs.greenhouse_employer_evidence import (
    GreenhouseEmployerEvidenceResolver,
)
from project_gideon.integrations.jobs.greenhouse_http import (
    ATSPageResponse,
    PageGet,
)
from project_gideon.models.ats_discovery import (
    ATSDiscoveryEvidence,
    ATSDiscoveryEvidenceType,
    ATSProvider,
    ATSRegistration,
    EmployerTarget,
)


GREENHOUSE_PUBLIC_HOSTS = frozenset(
    {
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
    }
)


_GREENHOUSE_LINK_PATTERN = re.compile(
    r"""https?://(?:boards|job-boards)\.greenhouse\.io/
        (?P<token>[A-Za-z0-9_-]+)
    """,
    re.IGNORECASE | re.VERBOSE,
)


DEFAULT_CAREER_PATHS = (
    "/careers",
    "/jobs",
)


JsonGet = Callable[
    [str],
    dict,
]


def default_page_get(
    url: str,
) -> ATSPageResponse:
    request = Request(
        url,
        headers={
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
            ),
            "User-Agent": "Project-Gideon/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(
            request,
            timeout=15,
        ) as response:
            body = response.read().decode(
                "utf-8",
                errors="replace",
            )

            final_url = response.geturl()

            status = getattr(
                response,
                "status",
                200,
            )
    except HTTPError as exc:
        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=exc.code,
            text="",
        )
    except URLError:
        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=0,
            text="",
        )

    return ATSPageResponse(
        requested_url=url,
        final_url=final_url,
        status_code=status,
        text=body,
    )


def default_greenhouse_probe(
    url: str,
) -> dict:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Project-Gideon/1.0",
        },
        method="GET",
    )

    with urlopen(
        request,
        timeout=15,
    ) as response:
        payload = response.read()

    import json

    decoded = json.loads(
        payload.decode(
            "utf-8"
        )
    )

    if not isinstance(
        decoded,
        dict,
    ):
        raise ValueError(
            "Greenhouse API response root must be an object."
        )

    return decoded


class GreenhouseATSDetector:
    """
    Deterministic detector for public employer Greenhouse boards.

    Detection requires provider evidence followed by successful structured
    API validation. A mere company-name guess is never enough.
    """

    def __init__(
        self,
        *,
        page_get: PageGet = default_page_get,
        json_get: JsonGet = default_greenhouse_probe,
        career_paths: tuple[
            str,
            ...,
        ] = DEFAULT_CAREER_PATHS,
    ) -> None:
        self._page_get = page_get
        self._json_get = json_get
        self._career_paths = career_paths
        self._employer_evidence = (
            GreenhouseEmployerEvidenceResolver(
                page_get=page_get
            )
        )

    def detect(
        self,
        target: EmployerTarget,
    ) -> ATSRegistration | None:
        for page_url in self._candidate_pages(
            target
        ):
            response = self._page_get(
                page_url
            )

            if (
                response.status_code < 200
                or response.status_code >= 400
            ):
                continue

            token = self._extract_token(
                response.final_url
            )

            evidence_url = response.final_url

            if token is None:
                token = self._extract_token(
                    response.text
                )

            if token is not None:
                registration = self._verify(
                    target=target,
                    token=token,
                    careers_url=evidence_url,
                )

                if registration is not None:
                    return registration

            listing_evidence = (
                self._employer_evidence
                .extract_listing_evidence(
                    response
                )
            )

            for listing in listing_evidence[:3]:
                embed = (
                    self._employer_evidence
                    .resolve_embed_evidence(
                        listing=listing
                    )
                )

                if embed is None:
                    continue

                registration = self._verify(
                    target=target,
                    token=embed.board_token,
                    careers_url=evidence_url,
                )

                if registration is not None:
                    return registration

        return None

    def _candidate_pages(
        self,
        target: EmployerTarget,
    ) -> list[str]:
        if target.careers_url is not None:
            return [
                str(
                    target.careers_url
                )
            ]

        assert target.domain is not None

        domain = (
            target.domain
            .strip()
            .lower()
            .removeprefix("https://")
            .removeprefix("http://")
            .strip("/")
        )

        base = f"https://{domain}"

        return [
            urljoin(
                base,
                path,
            )
            for path in self._career_paths
        ]

    @staticmethod
    def _extract_token(
        value: str,
    ) -> str | None:
        parsed = urlparse(
            value
        )

        host = (
            parsed.hostname
            or ""
        ).lower()

        if host in GREENHOUSE_PUBLIC_HOSTS:
            path_parts = [
                part
                for part in parsed.path.split("/")
                if part
            ]

            if path_parts:
                return path_parts[0]

        match = _GREENHOUSE_LINK_PATTERN.search(
            value
        )

        if match is None:
            return None

        return match.group(
            "token"
        )

    def _verify(
        self,
        *,
        target: EmployerTarget,
        token: str,
        careers_url: str,
    ) -> ATSRegistration | None:
        clean_token = token.strip()

        if not clean_token:
            return None

        api_url = (
            f"{GREENHOUSE_API_ROOT}/"
            f"{clean_token}/jobs?content=false"
        )

        try:
            raw = self._json_get(
                api_url
            )

            if not isinstance(
                raw,
                dict,
            ):
                return None

            if "jobs" not in raw:
                return None

            if not isinstance(
                raw["jobs"],
                list,
            ):
                return None

            response = (
                GreenhouseJobsResponse.model_validate(
                    raw
                )
            )
        except Exception:
            return None

        provider_url = (
            "https://job-boards.greenhouse.io/"
            f"{clean_token}"
        )

        evidence = [
            ATSDiscoveryEvidence(
                type=ATSDiscoveryEvidenceType.CAREERS_PAGE,
                url=careers_url,
                detail=(
                    "Employer careers surface supplied "
                    "Greenhouse provider evidence."
                ),
            ),
            ATSDiscoveryEvidence(
                type=ATSDiscoveryEvidenceType.PROVIDER_LINK,
                url=provider_url,
                detail=(
                    "Greenhouse board token extracted "
                    "from provider URL evidence."
                ),
            ),
            ATSDiscoveryEvidence(
                type=ATSDiscoveryEvidenceType.PROVIDER_API,
                url=api_url,
                detail=(
                    "Greenhouse public Job Board API "
                    "validated the registration; "
                    f"published_jobs={len(response.jobs)}."
                ),
            ),
        ]

        return ATSRegistration(
            company_name=target.company_name,
            provider=ATSProvider.GREENHOUSE,
            identifier=clean_token,
            careers_url=careers_url,
            provider_url=provider_url,
            api_url=api_url,
            evidence=evidence,
        )
