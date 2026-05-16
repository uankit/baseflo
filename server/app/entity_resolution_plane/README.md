# Entity Resolution Plane

The Entity Resolution Plane is Baseflo's boundary around Splink.

It plans and executes fuzzy matching across messy business sources: party names,
customer records, product names, email lists, offline ledgers, Shopify records,
and spreadsheet tabs.

The rest of Baseflo only sees typed contracts:

- `EntityResolutionPlan`
- `EntityResolutionDataset`
- `EntityResolutionExecution`
- `EntityMatch`
- `EntityCluster`

Splink settings dictionaries, linker objects, Pandas dataframes, and DuckDB API
objects stay inside `splink_engine.py`.
