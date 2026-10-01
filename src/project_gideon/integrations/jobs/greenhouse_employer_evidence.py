
from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import (
    parse_qs,
    urljoin,
    urlparse,
)

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
)

from project_gideon.integrations.jobs.greenhouse_http import (
    ATSPageResponse,
    PageGet,
)


_GREENHOUSE_EMBED_PATTERN = re.compile(
    r"""https?://job-boards\.greenhouse\.io/
        embed/job_app\?
        [^"'<> ]*
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


class EmployerGreenhouseListingEvidence(
    BaseModel,
):
    greenhouse_id: str = Field(
        min_length=1
    )

    slug: str = Field(
        min_length=1
    )

    source_url: HttpUrl


class GreenhouseEmbedEvidence(
    BaseModel,
):
    board_token: str = Field(
        min_length=1
    )

    job_id: str = Field(
        min_length=1
    )

    embed_url: HttpUrl

    employer_job_url: HttpUrl


class _NextDataCollector(
    HTMLParser,
):
    def __init__(
        self,
    ) -> None:
        super().__init__()

        self._capture = False
        self._parts: list[str] = []

        self.value: str | None = None

    def handle_starttag(
        self,
        tag,
        attrs,
    ) -> None:
        if tag.lower() != "script":
            return

        attributes = dict(
            attrs
        )

        if (
            attributes.get("id")
            == "__NEXT_DATA__"
        ):
            self._capture = True
            self._parts = []

    def handle_data(
        self,
        data,
    ) -> None:
        if self._capture:
            self._parts.append(
                data
            )

    def handle_endtag(
        self,
        tag,
    ) -> None:
        if (
            tag.lower() != "script"
            or not self._capture
        ):
            return

        self.value = "".join(
            self._parts
        )

        self._capture = False


def _walk(
    value,
):
    yield value

    if isinstance(
        value,
        dict,
    ):
        for child in value.values():
            yield from _walk(
                child
            )

    elif isinstance(
        value,
        list,
    ):
        for child in value:
            yield from _walk(
                child
            )


class GreenhouseEmployerEvidenceResolver:
    """
    Resolve Greenhouse registration evidence from employer-owned pages.

    The employer must explicitly publish a greenhouseId and the job-detail
    page must explicitly expose a Greenhouse application embed URL.

    Board tokens are never derived from company names.
    """

    def __init__(
        self,
        *,
        page_get: PageGet,
    ) -> None:
        self._page_get = page_get

    def extract_listing_evidence(
        self,
        page: ATSPageResponse,
    ) -> list[
        EmployerGreenhouseListingEvidence
    ]:
        collector = _NextDataCollector()

        collector.feed(
            page.text
        )

        if collector.value is None:
            return []

        try:
            root = json.loads(
                collector.value
            )
        except Exception:
            return []

        evidence = []

        for value in _walk(
            root
        ):
            if not isinstance(
                value,
                dict,
            ):
                continue

            greenhouse_id = value.get(
                "greenhouseId"
            )

            slug = value.get(
                "slug"
            )

            if (
                greenhouse_id is None
                or not isinstance(
                    slug,
                    str,
                )
                or not slug.strip()
            ):
                continue

            evidence.append(
                EmployerGreenhouseListingEvidence(
                    greenhouse_id=str(
                        greenhouse_id
                    ),
                    slug=slug.strip(),
                    source_url=page.final_url,
                )
            )

        return evidence

    def resolve_embed_evidence(
        self,
        *,
        listing: EmployerGreenhouseListingEvidence,
    ) -> GreenhouseEmbedEvidence | None:
        source = urlparse(
            str(
                listing.source_url
            )
        )

        path = source.path.rstrip("/")

        if path.endswith(
            "/search"
        ):
            base_path = path[
                : -len("/search")
            ]
        else:
            return None

        detail_path = (
            f"{base_path}/apply/"
            f"{listing.slug}/"
            f"{listing.greenhouse_id}"
        )

        employer_job_url = urljoin(
            str(
                listing.source_url
            ),
            detail_path,
        )

        page = self._page_get(
            employer_job_url
        )

        if (
            page.status_code < 200
            or page.status_code >= 400
        ):
            return None

        match = _GREENHOUSE_EMBED_PATTERN.search(
            page.text
        )

        if match is None:
            return None

        embed_url = unescape(
            match.group(
                0
            )
        )

        parsed = urlparse(
            embed_url
        )

        query = parse_qs(
            parsed.query
        )

        board_tokens = query.get(
            "for",
            [],
        )

        job_ids = query.get(
            "token",
            [],
        )

        if (
            len(board_tokens) != 1
            or len(job_ids) != 1
        ):
            return None

        board_token = board_tokens[0].strip()
        job_id = job_ids[0].strip()

        if (
            not board_token
            or not job_id
        ):
            return None

        if (
            job_id
            != listing.greenhouse_id
        ):
            return None

        return GreenhouseEmbedEvidence(
            board_token=board_token,
            job_id=job_id,
            embed_url=embed_url,
            employer_job_url=page.final_url,
        )
