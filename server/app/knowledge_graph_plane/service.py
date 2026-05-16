"""Knowledge Graph Plane service."""

from __future__ import annotations

from uuid import UUID

from app.business_surface_plane.contracts import BusinessSurfacePackage
from app.knowledge_graph_plane.contracts import KnowledgeGraphMaterialization
from app.knowledge_graph_plane.kuzu_store import KuzuKnowledgeGraphStore


def materialize_knowledge_graph(
    organization_id: UUID,
    *,
    business_surfaces: BusinessSurfacePackage | None,
    run_id: UUID | None = None,
    store: KuzuKnowledgeGraphStore | None = None,
) -> KnowledgeGraphMaterialization:
    graph_store = store or KuzuKnowledgeGraphStore()
    return graph_store.materialize(organization_id, business_surfaces, run_id=run_id)
