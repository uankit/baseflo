"""Prepare Action Plane v1 outputs without external side effects."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from app.action_plane.contracts import ActionRecord


def prepare_action_payload(
    action: ActionRecord,
    *,
    related_artifacts: dict[str, dict[str, Any]] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    related = related_artifacts or {}
    opts = options or {}
    if action.action_type == "email_draft":
        return _email_draft(action, related, opts)
    if action.action_type == "export_list":
        return _export_list(action, related, opts)
    if action.action_type == "save_cohort":
        return _save_cohort_payload(action, related, opts)
    raise ValueError(f"Unsupported action type: {action.action_type}")


def _email_draft(
    action: ActionRecord,
    related: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    rows = _rows(related)
    recipients = _recipients(rows)
    subject = _text(options.get("subject"), action.title)
    body_lines = [
        _text(options.get("greeting"), "Hi,"),
        "",
        action.summary or action.why,
        "",
        f"Why this: {action.why}",
    ]
    if rows:
        body_lines.extend(["", "Evidence sample:"])
        body_lines.extend(f"- {_row_summary(row)}" for row in rows[:5])
    body_lines.extend(["", "Best,"])
    return {
        "kind": "email_draft",
        "subject": subject,
        "body": "\n".join(line for line in body_lines if line is not None),
        "recipients": recipients,
        "recipient_count": len(recipients),
        "evidence_summary": _evidence_summary(rows),
        "requires_user_review": True,
    }


def _export_list(
    action: ActionRecord,
    related: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    rows = _rows(related)
    filename = _text(options.get("filename"), f"{_slug(action.title)}.csv")
    return {
        "kind": "export_list",
        "filename": filename,
        "format": "csv",
        "row_count": len(rows),
        "columns": _columns(rows),
        "csv": _csv(rows),
        "rows": rows,
    }


def _save_cohort_payload(
    action: ActionRecord,
    related: dict[str, dict[str, Any]],
    options: dict[str, Any],
) -> dict[str, Any]:
    rows = _rows(related)
    audience = _record(related.get("audience", {}).get("audience"))
    return {
        "kind": "save_cohort",
        "name": _text(options.get("name"), action.title),
        "description": _text(options.get("description"), action.summary or action.why),
        "audience": audience,
        "row_count": len(rows),
        "rows": rows,
    }


def _rows(related: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    table_payload = related.get("table", {})
    rows = table_payload.get("result_preview")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _recipients(rows: list[dict[str, Any]]) -> list[str]:
    recipients: list[str] = []
    for row in rows:
        for key, value in row.items():
            if "email" not in key.lower() or not isinstance(value, str) or "@" not in value:
                continue
            recipients.append(value.strip())
    return sorted(set(recipients))


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    return columns


def _csv(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    buffer = StringIO()
    columns = _columns(rows)
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _evidence_summary(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No row-level evidence was available in the preview."
    return f"{len(rows)} preview rows are attached as evidence."


def _row_summary(row: dict[str, Any]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in list(row.items())[:4])


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
    return slug or "baseflo_export"
