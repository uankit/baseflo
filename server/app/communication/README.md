# Baseflo Communication

This package is the protocol boundary for long-running Baseflo work.

## Standard

- Start work with REST JSON and return `RunAccepted`.
- Stream progress with SSE JSON `RunEvent` envelopes.
- Fetch state with REST JSON `RunState`.
- Fetch final artifacts through the domain result endpoint.

```text
POST /api/v1/<domain>/runs
GET  /api/v1/<domain>/runs/{run_id}
GET  /api/v1/<domain>/runs/{run_id}/events
GET  /api/v1/<domain>/runs/{run_id}/result
```

## Event Envelope

Every event carries:

- `run_id` and `organization_id` for tenant-safe routing
- `type` for machine handling
- `stage` for UI grouping
- `message` for human progress copy
- `progress` for coarse progress bars
- `payload` for typed stage details

Domain packages should accept a `RunEventPublisher` and publish through it. They should not import FastAPI, `StreamingResponse`, or transport-specific code.
