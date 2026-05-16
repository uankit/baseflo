# Data Profiler

The Data Profiler is the deterministic evidence layer between `data_plane` and
`agent_plane`.

It does not understand the business and does not produce insights. It measures
canonical data so agents can reason from facts instead of guessing.

It writes:

- `CanonicalField.observed_type`
- `CanonicalField.sample_values`
- `CanonicalField.profile["profiler"]`
- `CanonicalAsset.profile["profiler"]`
- `DataGraphEdge` rows with `created_by = "data_profiler_v1"` and predicate
  `RELATIONSHIP_CANDIDATE`

Evidence produced:

- field stats: null, blank, non-null, distinct, uniqueness, top values
- parse rates and observed type
- key, label, measure, timestamp, category, status, identifier candidates
- asset density, quality, primary key candidates, label candidates, freshness
- cross-asset relationship candidates from value overlap and cardinality

The Agent Plane consumes this evidence through canonical context packs.
