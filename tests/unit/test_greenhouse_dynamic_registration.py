
from project_gideon.integrations.jobs.greenhouse_discovery import (
    ATSPageResponse,
    GreenhouseATSDetector,
)
from project_gideon.models.ats_discovery import (
    ATSProvider,
    EmployerTarget,
)


SEARCH_HTML = """
<script id="__NEXT_DATA__" type="application/json">
{
  "props": {
    "pageProps": {
      "jobIndexData": {
        "listings": [
          {
            "greenhouseId": 8172510,
            "slug": "abuse-investigator"
          }
        ]
      }
    }
  }
}
</script>
"""


def test_detector_resolves_board_from_employer_owned_job_detail():
    calls = []

    def page_get(
        url,
    ):
        calls.append(
            url
        )

        if url.endswith(
            "/careers/search"
        ):
            return ATSPageResponse(
                requested_url=url,
                final_url=url,
                status_code=200,
                text=SEARCH_HTML,
            )

        return ATSPageResponse(
            requested_url=url,
            final_url=url,
            status_code=200,
            text=(
                '<iframe src="'
                'https://job-boards.greenhouse.io/'
                'embed/job_app?for=stripe'
                '&token=8172510">'
                '</iframe>'
            ),
        )

    detector = GreenhouseATSDetector(
        page_get=page_get,
        json_get=lambda url: {
            "jobs": [],
        },
    )

    registration = detector.detect(
        EmployerTarget(
            company_name="Stripe",
            careers_url=(
                "https://stripe.example/careers/search"
            ),
        )
    )

    assert registration is not None

    assert (
        registration.provider
        == ATSProvider.GREENHOUSE
    )

    assert (
        registration.identifier
        == "stripe"
    )

    assert len(calls) == 2
