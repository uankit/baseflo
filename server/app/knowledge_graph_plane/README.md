# Knowledge Graph Plane

The Knowledge Graph Plane is Baseflo's Kuzu-backed enterprise insight graph.

It materializes generated operating surfaces, dimensions, measures, cohorts,
candidate views, evidence refs, and action packs into an embedded property
graph.

This gives Baseflo a real graph substrate for questions like:

- What does this Receivables surface depend on?
- Which cohorts can trigger actions?
- Which evidence graphs support this recommendation?
- What related surfaces exist around the same entity?

The rest of the backend only depends on `KnowledgeGraphMaterialization`; Kuzu
connection objects and Cypher details stay inside this package.
