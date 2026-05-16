"""Convert supported action artifacts into Action Plane records."""

from __future__ import annotations

from typing import Any

from app.action_plane.contracts import ActionRecordDraft, ActionType
from app.artifact_plane.contracts import ArtifactRecord

SUPPORTED_ACTION_TYPES: set[ActionType] = {"email_draft", "export_list", "save_cohort"}


def action_draft_from_artifact(artifact: ArtifactRecord) -> ActionRecordDraft | None:
    if artifact.kind != "action":
        return None

    action_payload = _record(artifact.payload.get("action"))
    action_type = _supported_action_type(action_payload.get("action_type"))
    if action_type is None:
        return None

    action_id = _text(action_payload.get("action_id"), artifact.artifact_key)
    return ActionRecordDraft(
        artifact_id=artifact.id,
        run_id=artifact.run_id,
        action_key=f"{artifact.artifact_key}:{action_type}:{action_id}",
        action_type=action_type,
        title=_text(action_payload.get("title"), artifact.title),
        summary=_text(action_payload.get("why_now"), artifact.summary),
        why=_text(action_payload.get("why"), artifact.why),
        source_refs={
            **artifact.source_refs,
            "artifact_id": str(artifact.id),
            "artifact_key": artifact.artifact_key,
            "action_id": action_id,
        },
        payload={
            "artifact": artifact.model_dump(mode="json"),
            "action": action_payload,
        },
    )


def action_drafts_from_artifacts(artifacts: list[ArtifactRecord]) -> tuple[list[ActionRecordDraft], int]:
    drafts: list[ActionRecordDraft] = []
    skipped = 0
    for artifact in artifacts:
        draft = action_draft_from_artifact(artifact)
        if draft is None:
            if artifact.kind == "action":
                skipped += 1
            continue
        drafts.append(draft)
    return drafts, skipped


def _supported_action_type(value: Any) -> ActionType | None:
    return value if isinstance(value, str) and value in SUPPORTED_ACTION_TYPES else None


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback
