from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def _artifact(*, action_type: str = "email_draft", kind: str = "action"):
    from app.artifact_plane.contracts import ArtifactRecord

    now = datetime.now(UTC)
    return ArtifactRecord(
        id=uuid4(),
        organization_id=uuid4(),
        run_id=uuid4(),
        artifact_key="action:a1",
        kind=kind,
        status="new",
        title="Draft winback email",
        summary="Prepare a focused follow-up.",
        why="Customers are engaged but have not bought recently.",
        tags=["marketing", "customer"],
        priority=0.8,
        source_refs={"graph_id": "warm_inactive_customers"},
        payload={
            "action": {
                "action_id": "a1",
                "action_type": action_type,
                "title": "Draft winback email",
                "why": "Customers are engaged but have not bought recently.",
                "why_now": "The cohort is warm today.",
            }
        },
        fingerprint="abc",
        first_seen_at=now,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )


def _action(action_type: str = "email_draft"):
    from app.action_plane.contracts import ActionRecord

    now = datetime.now(UTC)
    return ActionRecord(
        id=uuid4(),
        organization_id=uuid4(),
        artifact_id=uuid4(),
        run_id=uuid4(),
        action_key=f"action:a1:{action_type}:a1",
        action_type=action_type,
        status="proposed",
        title="Draft winback email",
        summary="Prepare a focused follow-up.",
        why="Customers are engaged but have not bought recently.",
        source_refs={"graph_id": "warm_inactive_customers"},
        payload={},
        prepared_payload={},
        created_at=now,
        updated_at=now,
    )


def test_action_plane_syncs_only_supported_action_artifacts() -> None:
    from app.action_plane import action_drafts_from_artifacts

    drafts, skipped_count = action_drafts_from_artifacts(
        [
            _artifact(action_type="email_draft"),
            _artifact(action_type="manager_handoff"),
            _artifact(kind="table"),
        ]
    )

    assert len(drafts) == 1
    assert skipped_count == 1
    assert drafts[0].action_type == "email_draft"
    assert drafts[0].action_key == "action:a1:email_draft:a1"
    assert drafts[0].source_refs["graph_id"] == "warm_inactive_customers"


def test_action_plane_prepares_email_draft_from_related_rows() -> None:
    from app.action_plane import prepare_action_payload

    payload = prepare_action_payload(
        _action("email_draft"),
        related_artifacts={
            "table": {
                "result_preview": [
                    {"customer": "Niharini", "email": "nih@example.com", "days_since_order": 60},
                    {"customer": "Rishia", "email": "rishia@example.com", "days_since_order": 74},
                    {"customer": "Duplicate", "email": "nih@example.com"},
                ]
            }
        },
    )

    assert payload["kind"] == "email_draft"
    assert payload["recipient_count"] == 2
    assert payload["recipients"] == ["nih@example.com", "rishia@example.com"]
    assert "Why this:" in payload["body"]
    assert "Evidence sample:" in payload["body"]


def test_action_plane_prepares_export_list_csv() -> None:
    from app.action_plane import prepare_action_payload

    payload = prepare_action_payload(
        _action("export_list"),
        related_artifacts={
            "table": {
                "result_preview": [
                    {"customer": "Niharini", "pending_amount": 2400},
                    {"customer": "Rishia", "pending_amount": 1800},
                ]
            }
        },
    )

    assert payload["kind"] == "export_list"
    assert payload["row_count"] == 2
    assert payload["columns"] == ["customer", "pending_amount"]
    assert "customer,pending_amount" in payload["csv"]
    assert "Niharini,2400" in payload["csv"]


def test_action_plane_prepares_saved_cohort_payload() -> None:
    from app.action_plane import prepare_action_payload

    payload = prepare_action_payload(
        _action("save_cohort"),
        related_artifacts={
            "audience": {"audience": {"entity": "customer", "count": 2}},
            "table": {
                "result_preview": [
                    {"customer": "Niharini", "email": "nih@example.com"},
                    {"customer": "Rishia", "email": "rishia@example.com"},
                ]
            },
        },
        options={"name": "Warm inactive customers"},
    )

    assert payload["kind"] == "save_cohort"
    assert payload["name"] == "Warm inactive customers"
    assert payload["audience"] == {"entity": "customer", "count": 2}
    assert payload["row_count"] == 2
