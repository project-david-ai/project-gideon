from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from project_gideon.models import (
    ApprovalAction,
    ApprovalGrant,
    ApprovalRequest,
    ApprovalState,
)
from project_gideon.ports import ApprovalRepository


class ApprovalError(ValueError):
    pass


class ApprovalNotPending(ApprovalError):
    pass


class ApprovalGrantInvalid(ApprovalError):
    pass


class ApprovalService:
    """
    Deterministic approval authority.

    Agents may request approval, but only this service may create a grant.
    Grants are scoped to a tenant, action, and resource and are single-use.
    """

    def __init__(
        self,
        repository: ApprovalRepository,
        *,
        default_ttl: timedelta = timedelta(minutes=15),
    ) -> None:
        self._repository = repository
        self._default_ttl = default_ttl

    async def request(
        self,
        *,
        tenant_id: str,
        action: ApprovalAction,
        resource_id: str,
        requested_by_run_id: Optional[str] = None,
        requested_by_assistant_id: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            id=f"approval_{uuid4().hex}",
            tenant_id=tenant_id,
            action=action,
            resource_id=resource_id,
            requested_by_run_id=requested_by_run_id,
            requested_by_assistant_id=requested_by_assistant_id,
            summary=summary,
        )

        return await self._repository.save(request)

    async def approve(
        self,
        *,
        approval_id: str,
        tenant_id: str,
        ttl: Optional[timedelta] = None,
    ) -> ApprovalGrant:
        request = await self._repository.get(
            approval_id,
            tenant_id,
        )

        if request.state is not ApprovalState.PENDING:
            raise ApprovalNotPending(
                f"Approval request is not pending: {request.state.value}"
            )

        now = datetime.now(timezone.utc)

        approved_request = request.model_copy(
            update={
                "state": ApprovalState.APPROVED,
                "resolved_at": now,
            }
        )

        await self._repository.save(approved_request)

        lifetime = ttl or self._default_ttl

        grant = ApprovalGrant(
            id=f"grant_{uuid4().hex}",
            approval_request_id=request.id,
            tenant_id=request.tenant_id,
            action=request.action,
            resource_id=request.resource_id,
            issued_at=now,
            expires_at=now + lifetime,
        )

        return await self._repository.save_grant(
            grant
        )

    async def reject(
        self,
        *,
        approval_id: str,
        tenant_id: str,
    ) -> ApprovalRequest:
        request = await self._repository.get(
            approval_id,
            tenant_id,
        )

        if request.state is not ApprovalState.PENDING:
            raise ApprovalNotPending(
                f"Approval request is not pending: {request.state.value}"
            )

        rejected = request.model_copy(
            update={
                "state": ApprovalState.REJECTED,
                "resolved_at": datetime.now(timezone.utc),
            }
        )

        return await self._repository.save(rejected)

    async def consume(
        self,
        *,
        grant_id: str,
        tenant_id: str,
        action: ApprovalAction,
        resource_id: str,
        now: Optional[datetime] = None,
    ) -> ApprovalGrant:
        """
        Reload, validate, and durably consume a single-use grant.
        """

        grant = await self._repository.get_grant(
            grant_id,
            tenant_id,
        )

        self.validate_grant(
            grant,
            tenant_id=tenant_id,
            action=action,
            resource_id=resource_id,
            now=now,
        )

        request = await self._repository.get(
            grant.approval_request_id,
            tenant_id,
        )

        if request.state is not ApprovalState.APPROVED:
            raise ApprovalGrantInvalid(
                "Approval request is not in approved state."
            )

        consumed_grant = self.consume_grant(
            grant,
            now=now,
        )

        consumed_request = request.model_copy(
            update={
                "state": ApprovalState.CONSUMED,
            }
        )

        persisted_grant = (
            await self._repository.save_grant(
                consumed_grant
            )
        )

        await self._repository.save(
            consumed_request
        )

        return persisted_grant
    @staticmethod
    def validate_grant(
        grant: ApprovalGrant,
        *,
        tenant_id: str,
        action: ApprovalAction,
        resource_id: str,
        now: Optional[datetime] = None,
    ) -> None:
        current_time = now or datetime.now(timezone.utc)

        if grant.tenant_id != tenant_id:
            raise ApprovalGrantInvalid("Approval grant tenant mismatch.")

        if grant.action is not action:
            raise ApprovalGrantInvalid("Approval grant action mismatch.")

        if grant.resource_id != resource_id:
            raise ApprovalGrantInvalid("Approval grant resource mismatch.")

        if grant.is_consumed:
            raise ApprovalGrantInvalid("Approval grant has already been consumed.")

        if current_time >= grant.expires_at:
            raise ApprovalGrantInvalid("Approval grant has expired.")

    @staticmethod
    def consume_grant(
        grant: ApprovalGrant,
        *,
        now: Optional[datetime] = None,
    ) -> ApprovalGrant:
        if grant.is_consumed:
            raise ApprovalGrantInvalid("Approval grant has already been consumed.")

        return grant.model_copy(
            update={
                "consumed_at": now or datetime.now(timezone.utc),
            }
        )