# Lineage Plane

The Lineage Plane emits OpenLineage-style run, dataset, and column lineage.

It records:

- analysis graph inputs and outputs
- canonical asset references
- field-level mappings from execution lineage
- package-level lineage for semantic layer, surfaces, charts, ranking, entity
  resolution, and knowledge graph artifacts

The format is intentionally close to OpenLineage facets while remaining a local
typed contract that the rest of Baseflo can render directly.
