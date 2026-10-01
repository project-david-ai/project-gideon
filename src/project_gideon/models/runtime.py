from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ProjectDavidRuntimeBindings(BaseModel):
    """
    Resolved remote identities for Gideon's Project David composition.

    Logical names remain stable across environments; Project David resource
    IDs are instance-specific and are therefore runtime bindings rather than
    deployment configuration.
    """

    assistant_name: str
    assistant_id: str

    mcp_server_name: Optional[str] = None
    mcp_server_id: Optional[str] = None

    reconciled_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    meta_data: Dict[str, object] = Field(default_factory=dict)