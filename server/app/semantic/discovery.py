"""Semantic discovery — auto-label schema with business meaning."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic_ai import Agent

from app.config import get_settings
from app.connect.base import SourceSchema, TableSchema

logger = logging.getLogger("baseflo.discovery")
settings = get_settings()

DISCOVERY_PROMPT = """
You are a data semantics expert. Given raw table/column names and sample values,
label each column with its business meaning and suggest data types.

For each column, output:
- label: human-readable name
- data_type: one of [text, number, integer, date, datetime, boolean, money, email, url, uuid, category, json]
- semantic_type: business meaning, one of [customer_id, revenue, cost, order_date, quantity, status, email, phone, name, address, product_id, discount, tax, unknown]
- description: one sentence explaining what this column represents
- is_primary_key: true if this looks like an identifier column
- is_foreign_key: true if values reference another table's identifiers
- foreign_key_target: if is_foreign_key, guess the target table.column

Output JSON matching the expected schema exactly.
"""


class DiscoveryResult:
    """Result of semantic discovery for one table."""

    def __init__(self, table: TableSchema, columns: list[dict[str, Any]]) -> None:
        self.table = table
        self.columns = columns


class DiscoveryAgent:
    """LLM-powered schema semantic labeling."""

    def __init__(self) -> None:
        self._agent: Agent | None = None

    def _ensure_agent(self) -> Agent | None:
        """Lazy-init the LLM agent. Returns None if OpenAI is not configured."""
        if self._agent is not None:
            return self._agent

        # pydantic_ai reads OPENAI_API_KEY from os.environ.
        # Our Settings load from .env but don't mutate os.environ, so we
        # inject the key here if it's present in our config.
        if settings.openai_api_key and not os.environ.get("OPENAI_API_KEY"):
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key.get_secret_value()

        try:
            self._agent = Agent(
                model=settings.openai_model,
                system_prompt=DISCOVERY_PROMPT,
            )
            return self._agent
        except Exception as exc:
            logger.warning("OpenAI agent unavailable, using fallback labels: %s", exc)
            return None

    async def discover(self, schema: SourceSchema) -> list[DiscoveryResult]:
        """Label all tables in a source schema."""
        results: list[DiscoveryResult] = []
        for table in schema.tables:
            # Build input: table metadata + samples
            table_input = {
                "table_name": table.name,
                "row_count": table.row_count,
                "columns": [
                    {
                        "name": col.name,
                        "sample_values": col.sample_values[:5],
                        "nullable": col.nullable,
                    }
                    for col in table.columns
                ],
            }

            # TODO: call LLM with structured output
            # For now, return deterministic fallback labels
            columns = self._fallback_labels(table)
            results.append(DiscoveryResult(table, columns))
        return results

    def _fallback_labels(self, table: TableSchema) -> list[dict[str, Any]]:
        """Deterministic fallback when LLM is unavailable."""
        results = []
        for col in table.columns:
            label = col.name.replace("_", " ").title()
            data_type = "text"
            semantic_type = "unknown"

            name_lower = col.name.lower()
            samples = [str(v).lower() for v in col.sample_values if v]

            # Simple heuristics
            if any(k in name_lower for k in ("id", "_id", "uuid")):
                data_type = "uuid"
                semantic_type = "customer_id" if "customer" in name_lower else "product_id" if "product" in name_lower else "unknown"
            elif any(k in name_lower for k in ("email", "e_mail")):
                data_type = "email"
                semantic_type = "email"
            elif any(k in name_lower for k in ("price", "amount", "cost", "revenue", "total", "subtotal")):
                data_type = "money"
                semantic_type = "revenue"
            elif any(k in name_lower for k in ("date", "time", "created", "updated", "at")):
                data_type = "datetime"
                semantic_type = "order_date" if "order" in name_lower or "purchase" in name_lower else "unknown"
            elif any(k in name_lower for k in ("status", "state", "phase")):
                data_type = "category"
                semantic_type = "status"
            elif samples and all(s in ("true", "false", "1", "0", "yes", "no") for s in samples[:3]):
                data_type = "boolean"

            results.append({
                "name": col.name,
                "label": label,
                "description": f"Column '{col.name}' from source '{table.name}'",
                "data_type": data_type,
                "physical_type": "TEXT",
                "semantic_type": semantic_type,
                "nullable": col.nullable,
                "is_primary_key": name_lower in ("id", "_id", f"{table.name.lower()}_id"),
                "is_foreign_key": "_id" in name_lower and not name_lower in ("id", "_id"),
                "foreign_key_target": None,
                "sample_values": col.sample_values,
                "distinct_count": len(set(str(v) for v in col.sample_values)),
                "null_rate": None,
            })
        return results
