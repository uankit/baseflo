# Business View Plane

Business View Plane generates the founder-facing operating-room model from an
operating run.

It does not query source data directly and it does not own UI layout. It reads
semantic roles, business graph context, execution results, and run coverage,
then emits typed sections such as:

- Sales
- Receivables
- Inventory
- Customers & Parties
- Products & Items
- Expenses
- Profit & Loss
- Source Health & Coverage

Every section explains why it exists:

> Because this data has party names, bill amounts, and pending amounts, Baseflo
> built Receivables.

The UI can render this as the Operating Room / generated dashboard, and each
section carries suggested Ask questions and drill-down references.
