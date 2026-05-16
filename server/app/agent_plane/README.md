# Agent Plane

The Agent Plane is Baseflo's source-neutral reasoning layer. It starts after
`data_plane` has produced canonical assets, fields, snapshots, and graph edges.

Flow:

```text
canonical context
-> BusinessUnderstander
-> AssetSemanticist x asset
-> FieldSemanticist x asset
-> RelationshipMapper
-> RelationshipValidator
-> PatternProposer
-> Instantiator x hypothesis
-> ExecutionPlane
-> Hypothesizer / ChartSpecAgent / ActionDrafter / Narrator x result
-> BriefSynthesizer
```

Rules:

- Agents consume canonical ids, field ids, profiles, graph evidence, and memory.
- Agents never read connectors.
- Agents never execute SQL.
- Agents never fabricate result rows.
- Deterministic runtime validates relationships, plans, and query execution.
- Every agent has one responsibility, one typed output contract, and one prompt.
