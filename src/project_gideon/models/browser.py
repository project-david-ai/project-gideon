from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class BrowserSessionState(str, Enum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    FAILED = "failed"


class BrowserControlType(str, Enum):
    TEXTBOX = "textbox"
    TEXTAREA = "textarea"
    COMBOBOX = "combobox"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    BUTTON = "button"
    LINK = "link"
    FILE_INPUT = "file_input"
    OTHER = "other"


class BrowserActionType(str, Enum):
    NAVIGATE = "navigate"
    INSPECT = "inspect"
    FILL = "fill"
    CLICK = "click"
    SELECT = "select"
    UPLOAD = "upload"
    SCROLL = "scroll"
    WAIT = "wait"
    BACK = "back"


class BrowserSession(BaseModel):
    """
    Durable reference to a browser automation session.

    The underlying browser process is owned by the Playwright integration.
    Gideon stores only the session identity and lifecycle state.
    """

    id: str
    tenant_id: str
    application_id: Optional[str] = None

    state: BrowserSessionState = BrowserSessionState.CREATED

    current_url: Optional[str] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)


class BrowserControl(BaseModel):
    """
    Normalized representation of an interactive page control.
    """

    id: str
    control_type: BrowserControlType

    label: Optional[str] = None
    name: Optional[str] = None

    required: bool = False
    disabled: bool = False

    value: Optional[str] = None
    options: List[str] = Field(default_factory=list)

    meta_data: Dict[str, object] = Field(default_factory=dict)


class BrowserSnapshot(BaseModel):
    """
    Structured page state returned by the browser integration.
    """

    session_id: str
    url: str
    title: Optional[str] = None

    controls: List[BrowserControl] = Field(default_factory=list)

    validation_messages: List[str] = Field(default_factory=list)

    meta_data: Dict[str, object] = Field(default_factory=dict)


class BrowserAction(BaseModel):
    """
    Requested browser operation.

    The integration layer translates this contract into Playwright MCP calls.
    """

    action: BrowserActionType

    session_id: str

    control_id: Optional[str] = None
    value: Optional[str] = None
    url: Optional[str] = None
    file_id: Optional[str] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)


class BrowserActionResult(BaseModel):
    """
    Result of a browser action.
    """

    success: bool

    session_id: str
    action: BrowserActionType

    message: Optional[str] = None
    snapshot: Optional[BrowserSnapshot] = None

    meta_data: Dict[str, object] = Field(default_factory=dict)