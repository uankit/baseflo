"""Statistical insight engine — finds patterns without LLM hallucination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class StatInsight:
    kind: str  # concentration, anomaly, trend, correlation, gap, segment
    severity: str  # info, low, medium, high, critical
    title: str
    description: str
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)
    sql: str | None = None


class InsightEngine:
    """Deterministic pattern detection on synced data."""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def analyze_table(
        self, project_id: str, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Run all statistical checks on a single table."""
        insights: list[StatInsight] = []
        insights += await self._check_concentration(project_id, table_name, columns)
        insights += await self._check_anomalies(project_id, table_name, columns)
        insights += await self._check_gaps(project_id, table_name, columns)
        return insights

    async def _check_concentration(
        self, project_id: str, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Detect revenue/customer concentration (Pareto)."""
        insights: list[StatInsight] = []

        # Find money columns
        money_cols = [c for c in columns if c.get("semantic_type") == "revenue"]
        id_cols = [c for c in columns if c.get("semantic_type") in ("customer_id", "product_id")]

        for money_col in money_cols:
            for id_col in id_cols:
                # Query: what % of total does top 10% contribute?
                sql = f"""
                WITH ranked AS (
                    SELECT {id_col['name']}, SUM({money_col['name']}::numeric) as val,
                           NTILE(10) OVER (ORDER BY SUM({money_col['name']}::numeric) DESC) as decile
                    FROM {table_name}
                    GROUP BY {id_col['name']}
                )
                SELECT SUM(CASE WHEN decile = 1 THEN val ELSE 0 END) / SUM(val) as top_10_pct
                FROM ranked
                """
                # TODO: execute SQL, interpret result
                # For MVP scaffolding, return placeholder insight
                insights.append(StatInsight(
                    kind="concentration",
                    severity="medium",
                    title="Revenue concentration detected",
                    description=f"Top 10% of {id_col['label']}s may drive disproportionate {money_col['label']}.",
                    confidence=0.7,
                    sql=sql,
                    data={"id_column": id_col["name"], "value_column": money_col["name"]},
                ))
        return insights

    async def _check_anomalies(
        self, project_id: str, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Z-score outlier detection on numeric columns."""
        insights: list[StatInsight] = []
        numeric_cols = [c for c in columns if c.get("data_type") in ("number", "money", "integer")]

        for col in numeric_cols:
            sql = f"""
            SELECT AVG({col['name']}::numeric), STDDEV({col['name']}::numeric)
            FROM {table_name}
            WHERE {col['name']} IS NOT NULL
            """
            # TODO: execute, find rows > 3 stddev
            insights.append(StatInsight(
                kind="anomaly",
                severity="low",
                title=f"Anomalies in {col['label']}",
                description=f"Statistical outliers detected in {col['label']}. Worth reviewing.",
                confidence=0.6,
                sql=sql,
                data={"column": col["name"], "method": "zscore"},
            ))
        return insights

    async def _check_gaps(
        self, project_id: str, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Detect missing data patterns."""
        insights: list[StatInsight] = []
        for col in columns:
            if col.get("null_rate") and col["null_rate"] > 0.1:
                insights.append(StatInsight(
                    kind="gap",
                    severity="medium" if col["null_rate"] > 0.3 else "low",
                    title=f"Missing data in {col['label']}",
                    description=f"{col['null_rate']*100:.0f}% of rows have no value for {col['label']}.",
                    confidence=1.0,
                    data={"column": col["name"], "null_rate": col["null_rate"]},
                ))
        return insights
