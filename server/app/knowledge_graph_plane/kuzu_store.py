"""Kuzu persistence adapter for Baseflo's enterprise insight graph."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

from app.business_surface_plane.contracts import BusinessSurfacePackage
from app.config import get_settings
from app.knowledge_graph_plane.contracts import KnowledgeGraphMaterialization


class KuzuDependencyError(RuntimeError):
    """Raised when Kuzu is not installed in the backend runtime."""


class KuzuKnowledgeGraphStore:
    """Materialize surface insight graphs into an embedded Kuzu database."""

    def __init__(self, *, root: Path | None = None, connection_factory: Any = None) -> None:
        settings = get_settings()
        self.root = root or (Path(settings.data_dir).expanduser().resolve() / "kuzu")
        self.connection_factory = connection_factory

    def materialize(
        self,
        organization_id: UUID,
        package: BusinessSurfacePackage | None,
        *,
        run_id: UUID | None = None,
    ) -> KnowledgeGraphMaterialization:
        if package is None:
            return KnowledgeGraphMaterialization(
                status="failed",
                graph_path=str(self._graph_path(organization_id)),
                error="No business surface package supplied.",
            )
        try:
            conn = self._connection(organization_id)
            self._ensure_schema(conn)
            node_count = 0
            edge_count = 0
            prefix = f"{run_id}:" if run_id else ""
            for node in package.insight_graph.nodes:
                if self._execute_insert(
                    conn,
                    "CREATE (:BasefloNode {id: $id, run_id: $run_id, type: $type, label: $label, refs_json: $refs_json})",
                    {
                        "id": f"{prefix}{node.node_id}",
                        "run_id": str(run_id) if run_id else "",
                        "type": node.node_type,
                        "label": node.label,
                        "refs_json": json.dumps(node.refs, sort_keys=True, default=str),
                    },
                ):
                    node_count += 1
            for edge in package.insight_graph.edges:
                conn.execute(
                    """
                    MATCH (l:BasefloNode), (r:BasefloNode)
                    WHERE l.id = $left_id AND r.id = $right_id
                    CREATE (l)-[:BasefloEdge {
                        relationship: $relationship,
                        why: $why,
                        confidence: $confidence,
                        run_id: $run_id
                    }]->(r)
                    """,
                    {
                        "left_id": f"{prefix}{edge.left_node_id}",
                        "right_id": f"{prefix}{edge.right_node_id}",
                        "relationship": edge.relationship,
                        "why": edge.why,
                        "confidence": edge.confidence,
                        "run_id": str(run_id) if run_id else "",
                    },
                )
                edge_count += 1
            self._close(conn)
            return KnowledgeGraphMaterialization(
                status="completed",
                graph_path=str(self._graph_path(organization_id)),
                node_count=node_count,
                edge_count=edge_count,
                query_examples=[
                    "MATCH (s:BasefloNode)-[e:BasefloEdge]->(n:BasefloNode) RETURN s.label, e.relationship, n.label LIMIT 25",
                    "MATCH (s:BasefloNode {type: 'surface'})-[e]->(n) RETURN s.label, e.relationship, n.label",
                ],
            )
        except KuzuDependencyError:
            raise
        except Exception as exc:
            return KnowledgeGraphMaterialization(
                status="failed",
                graph_path=str(self._graph_path(organization_id)),
                error=str(exc),
            )

    def _connection(self, organization_id: UUID) -> Any:
        if self.connection_factory is not None:
            return self.connection_factory(self._graph_path(organization_id))
        try:
            import kuzu
        except ImportError as exc:
            raise KuzuDependencyError("Kuzu graph materialization requires the 'kuzu' package.") from exc
        self.root.mkdir(parents=True, exist_ok=True)
        db = kuzu.Database(str(self._graph_path(organization_id)))
        return kuzu.Connection(db)

    def _ensure_schema(self, conn: Any) -> None:
        self._execute_schema(
            conn,
            "CREATE NODE TABLE BasefloNode(id STRING, run_id STRING, type STRING, label STRING, refs_json STRING, PRIMARY KEY(id))",
        )
        self._execute_schema(
            conn,
            "CREATE REL TABLE BasefloEdge(FROM BasefloNode TO BasefloNode, relationship STRING, why STRING, confidence DOUBLE, run_id STRING)",
        )

    def _execute_schema(self, conn: Any, statement: str) -> None:
        try:
            conn.execute(statement)
        except Exception as exc:
            message = str(exc).lower()
            if "already exists" not in message and "duplicate" not in message:
                raise

    def _execute_insert(self, conn: Any, statement: str, parameters: dict[str, Any]) -> bool:
        try:
            conn.execute(statement, parameters)
            return True
        except Exception as exc:
            message = str(exc).lower()
            if "duplicate" in message or "already exists" in message:
                return False
            raise

    def _close(self, conn: Any) -> None:
        close = getattr(conn, "close", None)
        if callable(close):
            close()

    def _graph_path(self, organization_id: UUID) -> Path:
        return self.root / f"{organization_id}.kuzu"
