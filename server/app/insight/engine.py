"""Statistical insight engine — finds patterns without LLM hallucination."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class StatInsight:
    kind: str  # concentration, anomaly, trend, correlation, gap, segment, volume
    severity: str  # info, low, medium, high, critical
    title: str
    description: str
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)
    sql: str | None = None


class InsightEngine:
    """Deterministic pattern detection on synced data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def analyze_table(
        self,
        project_id: str,
        raw_table_name: str,
        columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Run all statistical checks on a single table.

        Each check is isolated — a failure in one does not block others.
        """
        insights: list[StatInsight] = []

        checks = [
            ("volume", self._check_volume),
            ("nulls", self._check_nulls),
            ("concentration", self._check_concentration),
            ("date_range", self._check_date_range),
            ("uniqueness", self._check_uniqueness),
        ]

        for check_name, check_fn in checks:
            try:
                if check_name == "volume":
                    result = await check_fn(raw_table_name)
                else:
                    result = await check_fn(raw_table_name, columns)
                insights.extend(result)
            except Exception:
                # Isolated failure — skip this check, keep the rest
                continue

        return insights

    async def _check_volume(self, table_name: str) -> list[StatInsight]:
        """Total row count."""
        sql = f'SELECT COUNT(*) FROM "{table_name}"'
        result = await self._session.execute(text(sql))
        count = result.scalar_one()

        return [StatInsight(
            kind="volume",
            severity="info",
            title=f"{count:,} rows in {table_name.replace('raw__', '').split('__', 1)[-1]}",
            description=f"Table contains {count:,} records after latest sync.",
            confidence=1.0,
            sql=sql,
            data={"row_count": count},
        )]

    async def _check_nulls(
        self, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Detect columns with high null rates."""
        insights: list[StatInsight] = []
        total_sql = f'SELECT COUNT(*) FROM "{table_name}"'
        result = await self._session.execute(text(total_sql))
        total = result.scalar_one()
        if total == 0:
            return insights

        for col in columns:
            col_name = col["name"]
            # Skip internal columns
            if col_name.startswith("_baseflo"):
                continue
            sql = f'SELECT COUNT(*) FROM "{table_name}" WHERE "{col_name}" IS NULL'
            result = await self._session.execute(text(sql))
            null_count = result.scalar_one()
            null_rate = null_count / total

            if null_rate > 0.3:
                severity = "high" if null_rate > 0.7 else "medium"
                insights.append(StatInsight(
                    kind="gap",
                    severity=severity,
                    title=f"{col['label']} is {null_rate*100:.0f}% empty",
                    description=f"{null_count:,} out of {total:,} rows have no value for {col['label']}. This may affect reporting accuracy.",
                    confidence=1.0,
                    sql=sql,
                    data={"column": col_name, "null_rate": null_rate, "null_count": null_count},
                ))
        return insights

    async def _check_concentration(
        self, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Pareto analysis on money columns grouped by ID columns."""
        insights: list[StatInsight] = []

        money_cols = [c for c in columns if c.get("semantic_type") == "revenue" or c.get("data_type") == "money"]
        id_cols = [c for c in columns if c.get("is_primary_key") or c.get("semantic_type") in ("customer_id", "product_id")]

        if not money_cols:
            return insights

        for money_col in money_cols:
            col_name = money_col["name"]
            # Total revenue
            total_sql = f'SELECT SUM(CAST("{col_name}" AS NUMERIC)) FROM "{table_name}" WHERE "{col_name}" IS NOT NULL'
            result = await self._session.execute(text(total_sql))
            total_revenue = result.scalar_one()
            if not total_revenue or total_revenue == 0:
                continue

            # Top 10% contributors
            id_col = id_cols[0]["name"] if id_cols else None
            if id_col:
                concentration_sql = f"""
                WITH ranked AS (
                    SELECT "{id_col}", SUM(CAST("{col_name}" AS NUMERIC)) as val,
                           NTILE(10) OVER (ORDER BY SUM(CAST("{col_name}" AS NUMERIC)) DESC) as decile
                    FROM "{table_name}"
                    WHERE "{col_name}" IS NOT NULL
                    GROUP BY "{id_col}"
                )
                SELECT COALESCE(SUM(CASE WHEN decile = 1 THEN val ELSE 0 END) / NULLIF(SUM(val), 0), 0) as top_10_pct,
                       COUNT(DISTINCT CASE WHEN decile = 1 THEN "{id_col}" END) as top_count
                FROM ranked
                """
                result = await self._session.execute(text(concentration_sql))
                row = result.one()
                top_pct = float(row.top_10_pct or 0)
                top_count = int(row.top_count or 0)

                if top_pct > 0.5:
                    insights.append(StatInsight(
                        kind="concentration",
                        severity="high" if top_pct > 0.8 else "medium",
                        title=f"Revenue is concentrated: top {top_count} contributors drive {top_pct*100:.0f}%",
                        description=f"Your {money_col['label']} is heavily skewed. {top_pct*100:.0f}% comes from just {top_count} records. Losing any of these would have a material impact.",
                        confidence=0.95,
                        sql=concentration_sql,
                        data={"top_10_pct": top_pct, "top_count": top_count, "value_column": col_name},
                    ))
            else:
                # No ID column — just report total
                insights.append(StatInsight(
                    kind="volume",
                    severity="info",
                    title=f"Total {money_col['label']}: {total_revenue:,.2f}",
                    description=f"Aggregated {money_col['label']} across all rows.",
                    confidence=1.0,
                    sql=total_sql,
                    data={"total": float(total_revenue), "column": col_name},
                ))

        return insights

    async def _check_date_range(
        self, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Detect date range and freshness."""
        insights: list[StatInsight] = []
        date_cols = [c for c in columns if c.get("data_type") in ("date", "datetime")]

        for col in date_cols:
            col_name = col["name"]
            sql = f"""
            SELECT MIN("{col_name}"), MAX("{col_name}"), COUNT(DISTINCT "{col_name}")
            FROM "{table_name}"
            WHERE "{col_name}" IS NOT NULL
            """
            result = await self._session.execute(text(sql))
            row = result.one()
            min_date, max_date, distinct_count = row

            if min_date and max_date:
                insights.append(StatInsight(
                    kind="trend",
                    severity="info",
                    title=f"{col['label']} spans {min_date} to {max_date}",
                    description=f"Data covers {distinct_count:,} unique dates. Most recent record: {max_date}.",
                    confidence=1.0,
                    sql=sql,
                    data={"min": str(min_date), "max": str(max_date), "distinct": distinct_count},
                ))
        return insights

    async def _check_uniqueness(
        self, table_name: str, columns: list[dict[str, Any]],
    ) -> list[StatInsight]:
        """Check primary key / ID column uniqueness."""
        insights: list[StatInsight] = []
        id_cols = [c for c in columns if c.get("is_primary_key") or c.get("semantic_type") == "customer_id"]

        for col in id_cols:
            col_name = col["name"]
            sql = f"""
            SELECT COUNT(*) as total, COUNT(DISTINCT "{col_name}") as unique_vals
            FROM "{table_name}"
            """
            result = await self._session.execute(text(sql))
            row = result.one()
            total, unique_vals = row
            if total == 0:
                continue

            dupes = total - unique_vals
            if dupes > 0:
                insights.append(StatInsight(
                    kind="anomaly",
                    severity="medium",
                    title=f"{dupes:,} duplicate {col['label']} values found",
                    description=f"Expected {col['label']} to be unique, but {dupes:,} rows share values with others. This may indicate data quality issues.",
                    confidence=1.0,
                    sql=sql,
                    data={"duplicates": dupes, "total": total, "unique": unique_vals},
                ))
        return insights
