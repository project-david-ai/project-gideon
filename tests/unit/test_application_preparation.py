import pytest

from project_gideon.integrations import (
    BrowserCapabilityDenied,
    FakePlaywrightAdapter,
    assert_preparation_action_allowed,
)
from project_gideon.models import (
    ApplicationPackage,
    ApplicationState,
    BrowserAction,
    BrowserActionType,
    BrowserControl,
    BrowserControlType,
    BrowserSnapshot,
    CandidateIdentity,
    CandidateProfile,
    JobApplication,
)
from project_gideon.repositories import (
    InMemoryApplicationRepository,
)
from project_gideon.services import (
    ApplicationPreparationService,
)


def make_candidate() -> CandidateProfile:
    return CandidateProfile(
        id="candidate_1",
        tenant_id="tenant_1",
        identity=CandidateIdentity(
            first_name="Test",
            last_name="Candidate",
            email="candidate@example.com",
        ),
    )


def make_application(
    *,
    state: ApplicationState = ApplicationState.PREPARING,
) -> JobApplication:
    return JobApplication(
        id="application_1",
        tenant_id="tenant_1",
        job_id="job_1",
        candidate_id="candidate_1",
        state=state,
    )


def make_package(
    candidate: CandidateProfile,
    *,
    answers=None,
) -> ApplicationPackage:
    return ApplicationPackage(
        application_id="application_1",
        job_id="job_1",
        candidate=candidate,
        application_url="https://example.com/apply",
        cv_file_id="file_cv_1",
        answers=answers or {},
    )


@pytest.mark.asyncio
async def test_preparation_fills_known_fields_and_uploads_cv():
    repository = InMemoryApplicationRepository()

    application = make_application()
    candidate = make_candidate()

    await repository.save(application)

    snapshot = BrowserSnapshot(
        session_id="placeholder",
        url="https://example.com/apply",
        controls=[
            BrowserControl(
                id="first_name",
                control_type=BrowserControlType.TEXTBOX,
                label="First name",
                required=True,
            ),
            BrowserControl(
                id="country",
                control_type=BrowserControlType.COMBOBOX,
                label="Country",
                required=True,
                options=["Argentina", "United Kingdom"],
            ),
            BrowserControl(
                id="resume",
                control_type=BrowserControlType.FILE_INPUT,
                label="Upload CV",
                required=True,
            ),
        ],
    )

    browser = FakePlaywrightAdapter(snapshot)

    service = ApplicationPreparationService(
        applications=repository,
        browser=browser,
    )

    result = await service.prepare(
        make_package(
            candidate,
            answers={
                "first_name": "Test",
                "country": "Argentina",
            },
        )
    )

    assert (
        result.application.state
        is ApplicationState.READY_FOR_REVIEW
    )

    assert result.unresolved_questions == []

    assert [
        action.action
        for action in result.actions
    ] == [
        BrowserActionType.FILL,
        BrowserActionType.SELECT,
        BrowserActionType.UPLOAD,
    ]

    assert result.application.browser_session_id is not None


@pytest.mark.asyncio
async def test_unknown_required_field_moves_application_to_needs_input():
    repository = InMemoryApplicationRepository()

    application = make_application()
    candidate = make_candidate()

    await repository.save(application)

    snapshot = BrowserSnapshot(
        session_id="placeholder",
        url="https://example.com/apply",
        controls=[
            BrowserControl(
                id="salary_expectation",
                control_type=BrowserControlType.TEXTBOX,
                label="Salary expectation",
                required=True,
            ),
        ],
    )

    browser = FakePlaywrightAdapter(snapshot)

    service = ApplicationPreparationService(
        applications=repository,
        browser=browser,
    )

    result = await service.prepare(
        make_package(candidate)
    )

    assert (
        result.application.state
        is ApplicationState.NEEDS_INPUT
    )

    assert len(result.unresolved_questions) == 1
    assert (
        result.unresolved_questions[0].field_id
        == "salary_expectation"
    )


@pytest.mark.asyncio
async def test_checkbox_is_not_silently_clicked():
    repository = InMemoryApplicationRepository()

    application = make_application()
    candidate = make_candidate()

    await repository.save(application)

    snapshot = BrowserSnapshot(
        session_id="placeholder",
        url="https://example.com/apply",
        controls=[
            BrowserControl(
                id="legal_attestation",
                control_type=BrowserControlType.CHECKBOX,
                label="I certify the above information",
                required=True,
            ),
        ],
    )

    browser = FakePlaywrightAdapter(snapshot)

    service = ApplicationPreparationService(
        applications=repository,
        browser=browser,
    )

    result = await service.prepare(
        make_package(
            candidate,
            answers={
                "legal_attestation": True,
            },
        )
    )

    assert browser.actions == []

    assert (
        result.application.state
        is ApplicationState.NEEDS_INPUT
    )


def test_generic_click_is_denied_during_preparation():
    action = BrowserAction(
        action=BrowserActionType.CLICK,
        session_id="browser_1",
        control_id="submit",
    )

    with pytest.raises(
        BrowserCapabilityDenied,
        match="not permitted",
    ):
        assert_preparation_action_allowed(action)


@pytest.mark.asyncio
async def test_preparation_can_resume_from_needs_input():
    repository = InMemoryApplicationRepository()

    application = make_application(
        state=ApplicationState.NEEDS_INPUT
    )

    candidate = make_candidate()

    await repository.save(application)

    snapshot = BrowserSnapshot(
        session_id="placeholder",
        url="https://example.com/apply",
        controls=[
            BrowserControl(
                id="notice_period",
                control_type=BrowserControlType.TEXTBOX,
                label="Notice period",
                required=True,
            ),
        ],
    )

    browser = FakePlaywrightAdapter(snapshot)

    service = ApplicationPreparationService(
        applications=repository,
        browser=browser,
    )

    result = await service.prepare(
        make_package(
            candidate,
            answers={
                "notice_period": "Immediate",
            },
        )
    )

    assert (
        result.application.state
        is ApplicationState.READY_FOR_REVIEW
    )