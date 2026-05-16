# Operating Pipeline

The Operating Pipeline is the end-to-end run envelope for Baseflo.

It coordinates independent packages:

```text
data_plane ready
-> data_profiler
-> agent_plane planning
-> execution_plane
-> agent_plane result agents
-> business_view_plane
-> business_surface_plane
-> entity_resolution_plane
-> knowledge_graph_plane
-> artifact_plane
-> action_plane
-> OperatingRunResult
```

Modes:

- `scan`: runs without a user question. This powers Brief and Inbox.
- `ask`: runs with a user question. The question is passed into the Agent Plane
  so hypotheses and narration stay focused on what the user asked.

Rules:

- The pipeline does not inspect connectors.
- The pipeline does not compile SQL.
- The pipeline does not repair failed agent plans.
- Failed plan execution is returned as a typed `PlanExecution` failure.
- Result-side agents only receive real `AnalysisResultRef` objects.
- No fake brief, chart, action, or narrative is created when execution fails.
