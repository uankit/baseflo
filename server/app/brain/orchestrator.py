"""Brain orchestrator — coordinates agents and deterministic execution."""

from __future__ import annotations

from typing import Any

from app.db.session import open_session
from app.insight.engine import InsightEngine, StatInsight
from app.semantic.discovery import DiscoveryAgent, DiscoveryResult


class BrainOrchestrator:
    """The central brain. Agents propose, this validates and executes."""

    def __init__(self) -> None:
        self.discovery = DiscoveryAgent()

    async def on_source_synced(self, source_id: str) -> None:
        """Triggered after a successful sync. Runs the full brain pipeline."""
        async with open_session() as session:
            # 1. Load source + project
            from app.db.models import DataSource, SemanticTable
            from sqlalchemy import select

            result = await session.execute(
                select(DataSource).where(DataSource.id == source_id)
            )
            source = result.scalar_one_or_none()
            if source is None:
                return

            # 2. Introspect source schema (if not already cached)
            from app.connect.registry import get as get_connector
            connector = get_connector(source.kind)
            schema = await connector.introspect(source.config)

            # 3. DiscoveryAgent → semantic labels
            discovered = await self.discovery.discover(schema)

            # 4. Persist semantic layer
            for d in discovered:
                sem_table = SemanticTable(
                    project_id=source.project_id,
                    source_id=source.id,
                    name=d.table.name,
                    label=d.table.name.replace("_", " ").title(),
                    source_table_name=d.table.name,
                    row_count=d.table.row_count,
                )
                session.add(sem_table)
                await session.flush()

                from app.db.models import SemanticColumn
                for col_data in d.columns:
                    sem_col = SemanticColumn(
                        table_id=sem_table.id,
                        **{k: v for k, v in col_data.items() if k != "sample_values"},
                        sample_values=col_data.get("sample_values", []),
                    )
                    session.add(sem_col)

            # 5. InsightEngine → statistical patterns
            engine = InsightEngine(session)
            all_insights: list[StatInsight] = []
            for d in discovered:
                raw_table = f"raw__{source.project_id.hex}__{d.table.name}"
                cols = [{k: v for k, v in c.items()} for c in d.columns]
                table_insights = await engine.analyze_table(
                    str(source.project_id), raw_table, cols,
                )
                all_insights.extend(table_insights)

            # 6. Persist insights
            from app.db.models import Insight
            for ins in all_insights:
                insight = Insight(
                    project_id=source.project_id,
                    kind=ins.kind,
                    severity=ins.severity,
                    title=ins.title,
                    description=ins.description,
                    confidence=ins.confidence,
                    sql=ins.sql,
                    data=ins.data,
                )
                session.add(insight)

            # 7. TODO: push new insights via WebSocket
            # from app.ws import manager
            # await manager.push_insight(...)

    async def answer_question(self, project_id: str, question: str) -> dict[str, Any]:
        """Natural language query — agent generates SQL, deterministic executor runs it."""
        # TODO: QueryAgent generates SQL → execute → narrative
        return {"answer": "Not yet implemented", "sql": None}
