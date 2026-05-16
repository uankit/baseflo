# Action Plane

Action Plane v1 turns supported action artifacts into operational records.

Supported v1 actions:

- `email_draft`
- `export_list`
- `save_cohort`

There is no external sending, delegation, scheduler, ad execution, or third-party
writeback here. `prepare` creates a usable internal payload only:

- email subject/body/recipients preview
- CSV export payload
- saved cohort row set

Lifecycle is intentionally small:

- `proposed`
- `prepared`
- `completed`
- `dismissed`
