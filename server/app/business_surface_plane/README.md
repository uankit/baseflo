# Business Surface Plane

The Business Surface Plane turns a completed operating run into generated
workbenches: Receivables, Inventory, Sales, P&L, Customers/Parties, Products,
Expenses, Operations, and source coverage.

It is deterministic. It does not execute SQL, call agents, or invent fields.
It consumes:

- business view sections
- semantic asset roles
- semantic field roles
- materialized execution refs
- graph refs and pattern hypotheses

It emits:

- `BusinessSurfacePackage`
- surface dimensions and measures
- candidate drilldown views
- business cohorts
- supported bulk action packs
- an insight graph linking surfaces, fields, cohorts, evidence, and actions

The algorithms are inspired by semantic table interpretation, data profiling,
data-cube drilldowns, automatic insight ranking, and enterprise knowledge graph
systems. Splink and Kuzu are attached in separate planes so this package can
emit stable typed surface plans without leaking external engine APIs.
