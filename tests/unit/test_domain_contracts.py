from datetime import datetime, timedelta, timezone

from project_gideon.models import (
    ApprovalAction,
    ApprovalGrant,
    ApprovalRequest,
    ApprovalState,
    BrowserAction,
    BrowserActionResult,
    BrowserActionType,
    BrowserControl,
    BrowserControlType,
    BrowserSession,
    BrowserSessionState,
    BrowserSnapshot,
)


def test_approval_contract_is_scoped_to_action_and_resource():
    request = ApprovalRequest(
        id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
    )

    assert request.state is ApprovalState.PENDING
    assert request.action is ApprovalAction.SUBMIT_APPLICATION
    assert request.resource_id == "application_1"


def test_approval_grant_tracks_consumption():
    now = datetime.now(timezone.utc)

    grant = ApprovalGrant(
        id="grant_1",
        approval_request_id="approval_1",
        tenant_id="tenant_1",
        action=ApprovalAction.SUBMIT_APPLICATION,
        resource_id="application_1",
        expires_at=now + timedelta(minutes=10),
    )

    assert grant.is_consumed is False

    consumed = grant.model_copy(
        update={"consumed_at": now},
    )

    assert consumed.is_consumed is True


def test_browser_snapshot_normalizes_interactive_controls():
    session = BrowserSession(
        id="browser_1",
        tenant_id="tenant_1",
        application_id="application_1",
        state=BrowserSessionState.ACTIVE,
        current_url="https://example.com/apply",
    )

    control = BrowserControl(
        id="control_1",
        control_type=BrowserControlType.TEXTBOX,
        label="First name",
        required=True,
    )

    snapshot = BrowserSnapshot(
        session_id=session.id,
        url=session.current_url,
        controls=[control],
    )

    assert snapshot.controls[0].label == "First name"
    assert snapshot.controls[0].required is True


def test_browser_action_contract():
    action = BrowserAction(
        action=BrowserActionType.FILL,
        session_id="browser_1",
        control_id="control_1",
        value="Test",
    )

    result = BrowserActionResult(
        success=True,
        session_id=action.session_id,
        action=action.action,
        message="Field populated.",
    )

    assert result.success is True
    assert result.action is BrowserActionType.FILL