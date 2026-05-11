"""Brain orchestrator — coordinates agents and deterministic execution."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.connect.registry import get as get_connector
from app.db.models import (
    DataSource,
    Insight,
    SemanticColumn,
    SemanticTable,
)
from app.db.session import open_session
from app.insight.engine import InsightEngine, StatInsight
from app.semantic.discovery import DiscoveryAgent, DiscoveryResult
from app.ws import manager as ws_manager

logger = logging.getLogger("baseflo.brain")


class BrainOrchestrator:
    """The central brain. Agents propose, this validates and executes."""

    def __init__(self) -> None:
        self.discovery = DiscoveryAgent()

    async def on_source_synced(self, source_id: str) -> list[Insight]:
        """Triggered after a successful sync. Runs the full brain pipeline."""
        logger.info("[brain] starting pipeline for source=%s", source_id)
        async with open_session() as session:
            # 1. Load source + project
            result = await session.execute(
                select(DataSource).where(DataSource.id == source_id)
            )
            source = result.scalar_one_or_none()
            if source is None:
                logger.warning("[brain] source not found: %s", source_id)
                return []

            # 2. Introspect source schema
            logger.info("[brain] introspecting source=%s", source_id)
            connector = get_connector(source.kind)
            schema = await connector.introspect(source.config)
            logger.info("[brain] found %d tables for source=%s", len(schema.tables), source_id)

            # 3. DiscoveryAgent → semantic labels
            logger.info("[brain] running discovery for source=%s", source_id)
            discovered: list[DiscoveryResult] = await self.discovery.discover(schema)
            logger.info("[brain] discovery returned %d tables for source=%s", len(discovered), source_id)

            # 4. Persist semantic layer
            logger.info("[brain] persisting semantic layer for source=%s", source_id)
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

                for col_data in d.columns:
                    sem_col = SemanticColumn(
                        table_id=sem_table.id,
                        name=col_data["name"],
                        label=col_data["label"],
                        description=col_data.get("description"),
                        data_type=col_data["data_type"],
                        physical_type=col_data.get("physical_type", "TEXT"),
                        nullable=col_data.get("nullable", True),
                        is_primary_key=col_data.get("is_primary_key", False),
                        is_foreign_key=col_data.get("is_foreign_key", False),
                        foreign_key_target=col_data.get("foreign_key_target"),
                        semantic_type=col_data.get("semantic_type"),
                        sample_values=col_data.get("sample_values", []),
                        distinct_count=col_data.get("distinct_count"),
                        null_rate=col_data.get("null_rate"),
                    )
                    session.add(sem_col)

            # 5. InsightEngine → statistical patterns on raw data
            logger.info("[brain] running insight engine for source=%s", source_id)
            engine = InsightEngine(session)
            all_insights: list[StatInsight] = []
            for d in discovered:
                raw_table = f"raw__{source.project_id.hex}__{d.table.name}"
                cols = [dict(c) for c in d.columns]
                logger.info("[brain] analyzing table=%s (%d cols) for source=%s", raw_table, len(cols), source_id)
                table_insights = await engine.analyze_table(
                    str(source.project_id), raw_table, cols,
                )
                logger.info("[brain] table=%s generated %d insights for source=%s", raw_table, len(table_insights), source_id)
                all_insights.extend(table_insights)

            # 6. Persist insights
            logger.info("[brain] persisting %d insights for source=%s", len(all_insights), source_id)
            persisted_insights: list[Insight] = []
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
                persisted_insights.append(insight)

            await session.commit()
            logger.info("[brain] committed %d insights for source=%s", len(persisted_insights), source_id)

            # 7. Push new insights via WebSocket
            logger.info("[brain] pushing %d insights via WS for project=%s", len(persisted_insights), source.project_id)
            for ins in persisted_insights:
                await ws_manager.push_insight(
                    str(source.project_id),
                    {
                        "id": str(ins.id),
                        "kind": ins.kind,
                        "severity": ins.severity,
                        "title": ins.title,
                        "description": ins.description,
                        "confidence": float(ins.confidence) if ins.confidence else 0,
                        "data": ins.data,
                        "sql": ins.sql,
                        "created_at": ins.created_at.isoformat() if ins.created_at else None,
                    },
                )

            logger.info("[brain] pipeline complete for source=%s", source_id)
            return persisted_insights

    async def answer_question(self, project_id: str, question: str) -> dict[str, Any]:
        """Natural language query — agent generates SQL, deterministic executor runs it."""
        # TODO: QueryAgent generates SQL → execute → narrative
        return {"answer": "Not yet implemented", "sql": None}
