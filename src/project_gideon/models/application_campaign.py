from __future__ import annotations

from enum import Enum
from typing import Self

from pydantic import BaseModel, model_validator

from project_gideon.models.application import (
    JobApplication,
)


class ApplicationCampaignAction(str, Enum):
    SHORTLIST = "shortlist"
    START_PREPARATION = "start_preparation"


class ApplicationCampaignRequest(BaseModel):
    """
    Typed supervisor boundary for durable application-campaign mutations.
    """

    tenant_id: str
    action: ApplicationCampaignAction

    job_id: str | None = None
    candidate_id: str | None = None
    application_id: str | None = None

    @model_validator(mode="after")
    def validate_action_identity(
        self,
    ) -> Self:
        if self.action is ApplicationCampaignAction.SHORTLIST:
            if not self.job_id:
                raise ValueError(
                    "Shortlist requires job_id."
                )

            if not self.candidate_id:
                raise ValueError(
                    "Shortlist requires candidate_id."
                )

        if (
            self.action
            is ApplicationCampaignAction.START_PREPARATION
            and not self.application_id
        ):
            raise ValueError(
                "Start preparation requires application_id."
            )

        return self


class ApplicationCampaignResult(BaseModel):
    """
    Typed result returned to the career supervisor after a campaign mutation.
    """

    action: ApplicationCampaignAction
    application: JobApplication
