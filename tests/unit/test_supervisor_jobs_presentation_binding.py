
class BindableJobsService:
    def __init__(
        self,
    ):
        self.sink = "unset"

    def bind_presentation(
        self,
        *,
        presentation_sink,
    ):
        self.sink = presentation_sink


def test_jobs_service_exposes_presentation_binding_contract():
    from project_gideon.services.delegation import (
        JobsDelegationService,
    )

    class Port:
        def __init__(
            self,
        ):
            self.sink = None

        def bind_presentation(
            self,
            *,
            presentation_sink,
        ):
            self.sink = presentation_sink

        def delegate_jobs(
            self,
            request,
        ):
            raise AssertionError(
                "not used"
            )

    port = Port()

    service = JobsDelegationService(
        port
    )

    sink = lambda event: None

    service.bind_presentation(
        presentation_sink=sink
    )

    assert port.sink is sink
