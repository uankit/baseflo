"""MembershipRepository — lookups for the auth path.

The list-by-user query goes through `app_get_user_memberships(uuid)`
(SECURITY DEFINER) so the auth middleware can resolve memberships before
RLS scope is established.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = ["MembershipRepository", "ResolvedMembership"]


@dataclass(frozen=True, slots=True)
class ResolvedMembership:
    """Auth-shaped membership: enough for routing + RBAC, no ORM coupling."""

    membership_id: UUID
    organization_id: UUID
    organization_slug: str
    role: str
    organization_name: str = ""
    plan: str = "hobby"
    region: str = "us-east-1"
    status: str = "active"
    organization_created_at: datetime | None = None


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: UUID) -> list[ResolvedMembership]:
        result = await self._session.execute(
            text(
                "SELECT membership_id, organization_id, organization_slug, "
                "organization_name, role, plan, region, status, organization_created_at "
                "FROM app_get_user_memberships(:uid)"
            ),
            {"uid": str(user_id)},
        )
        return [
            ResolvedMembership(
                membership_id=row["membership_id"],
                organization_id=row["organization_id"],
                organization_slug=row["organization_slug"],
                organization_name=row["organization_name"],
                role=row["role"],
                plan=row["plan"],
                region=row["region"],
                status=row["status"],
                organization_created_at=row["organization_created_at"],
            )
            for row in result.mappings().all()
        ]
