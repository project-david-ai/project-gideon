
from project_gideon.integrations.jobs.greenhouse_discovery import (
    ATSPageResponse,
)
from project_gideon.integrations.jobs.greenhouse_employer_evidence import (
    GreenhouseEmployerEvidenceResolver,
)


SEARCH_HTML = """
<html>
<body>
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "jobIndexData": {
        "listings": [
          {
            "greenhouseId": 8172510,
            "title": "Abuse Investigator",
            "slug": "abuse-investigator"
          }
        ]
      }
    }
  }
}
</script>
</body>
</html>
"""


def test_extracts_employer_published_greenhouse_listing():
    resolver = GreenhouseEmployerEvidenceResolver(
        page_get=lambda url: None
    )

    evidence = resolver.extract_listing_evidence(
        ATSPageResponse(
            requested_url=(
                "https://stripe.example/careers/search"
            ),
            final_url=(
                "https://stripe.example/careers/search"
            ),
            status_code=200,
            text=SEARCH_HTML,
        )
    )

    assert len(evidence) == 1

    assert (
        evidence[0].greenhouse_id
        == "8172510"
    )

    assert (
        evidence[0].slug
        == "abuse-investigator"
    )


def test_resolves_board_token_from_employer_job_embed():
    calls = []

    def page_get(
        url,
    ):
        calls.append(
            url
        )

        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                '<iframe src="'
                'https://job-boards.greenhouse.io/'
                'embed/job_app?for=stripe'
                '&amp;token=8172510">'
                '</iframe>'
            ),
        )

    resolver = GreenhouseEmployerEvidenceResolver(
        page_get=page_get
    )

    listing = resolver.extract_listing_evidence(
        ATSPageResponse(
            requested_url=(
                "https://stripe.example/careers/search"
            ),
            final_url=(
                "https://stripe.example/careers/search"
            ),
            status_code=200,
            text=SEARCH_HTML,
        )
    )[0]

    evidence = resolver.resolve_embed_evidence(
        listing=listing
    )

    assert evidence is not None

    assert (
        evidence.board_token
        == "stripe"
    )

    assert (
        evidence.job_id
        == "8172510"
    )

    assert calls == [
        (
            "https://stripe.example/"
            "careers/apply/"
            "abuse-investigator/"
            "8172510"
        )
    ]


def test_rejects_embed_when_job_id_does_not_match_employer_evidence():
    resolver = GreenhouseEmployerEvidenceResolver(
        page_get=lambda url: ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                '<iframe src="'
                'https://job-boards.greenhouse.io/'
                'embed/job_app?for=stripe'
                '&token=9999999">'
                '</iframe>'
            ),
        )
    )

    listing = resolver.extract_listing_evidence(
        ATSPageResponse(
            requested_url=(
                "https://stripe.example/careers/search"
            ),
            final_url=(
                "https://stripe.example/careers/search"
            ),
            status_code=200,
            text=SEARCH_HTML,
        )
    )[0]

    assert (
        resolver.resolve_embed_evidence(
            listing=listing
        )
        is None
    )
