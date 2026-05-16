"""Action Plane v1 service."""

from __future__ import annotations

from uuid import UUID

from app.action_plane.contracts import (
    ActionPlaneRunResult,
    ActionPrepareRequest,
    ActionRecord,
)
from app.action_plane.preparer import prepare_action_payload
from app.action_plane.store import (
    load_action,
    load_related_action_artifacts,
    mark_action_completed,
    mark_action_dismissed,
    mark_action_prepared,
    upsert_action_drafts,
    upsert_saved_cohort,
)
from app.action_plane.sync import action_drafts_from_artifacts
from app.artifact_plane.contracts import ArtifactPlaneRunResult


async def sync_actions_from_artifacts(
    organization_id: UUID,
    *,
    artifacts: ArtifactPlaneRunResult,
) -> ActionPlaneRunResult:
    drafts, skipped_count = action_drafts_from_artifacts(artifacts.artifacts)
    actions, created_count, updated_count = await upsert_action_drafts(
        organization_id,
        drafts=drafts,
    )
    return ActionPlaneRunResult(
        organization_id=organization_id,
        run_id=artifacts.run_id,
        actions=actions,
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
    )


async def prepare_action(
    organization_id: UUID,
    *,
    action_id: UUID,
    request: ActionPrepareRequest | None = None,
) -> ActionRecord:
    action = await load_action(organization_id, action_id=action_id)
    related = await load_related_action_artifacts(organization_id, action=action)
    prepared_payload = prepare_action_payload(
        action,
        related_artifacts=related,
        options=(request.options if request else {}),
    )
    if action.action_type == "save_cohort":
        cohort = await upsert_saved_cohort(
            organization_id,
            action=action,
            prepared_payload=prepared_payload,
        )
        prepared_payload = {
            **prepared_payload,
            "cohort_id": str(cohort.id),
            "cohort_key": cohort.cohort_key,
        }
    return await mark_action_prepared(
        organization_id,
        action_id=action_id,
        prepared_payload=prepared_payload,
    )


async def complete_action(organization_id: UUID, *, action_id: UUID) -> ActionRecord:
    return await mark_action_completed(organization_id, action_id=action_id)


async def dismiss_action(organization_id: UUID, *, action_id: UUID) -> ActionRecord:
    return await mark_action_dismissed(organization_id, action_id=action_id)
