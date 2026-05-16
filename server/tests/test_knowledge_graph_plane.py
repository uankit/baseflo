from __future__ import annotations

from pathlib import Path
from uuid import uuid4


class FakeKuzuConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, dict | None]] = []

    def execute(self, statement: str, parameters: dict | None = None) -> None:
        self.statements.append((statement, parameters))

    def close(self) -> None:
        pass


def test_kuzu_store_materializes_surface_insight_graph() -> None:
    from app.business_surface_plane import mine_business_surfaces
    from app.knowledge_graph_plane import KuzuKnowledgeGraphStore
    from tests.test_business_surface_plane import _receivables_run

    connection = FakeKuzuConnection()
    surfaces = mine_business_surfaces(_receivables_run())
    store = KuzuKnowledgeGraphStore(root=Path("/tmp/baseflo-kuzu-test"), connection_factory=lambda path: connection)

    result = store.materialize(uuid4(), surfaces, run_id=uuid4())

    assert result.status == "completed"
    assert result.node_count == len(surfaces.insight_graph.nodes)
    assert result.edge_count == len(surfaces.insight_graph.edges)
    assert any("CREATE NODE TABLE" in statement for statement, _params in connection.statements)
    assert any("CREATE REL TABLE" in statement for statement, _params in connection.statements)
    assert any(params and "refs_json" in params for _statement, params in connection.statements)
