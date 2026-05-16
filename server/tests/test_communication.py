from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_run_event_bus_records_and_streams_lifecycle_events() -> None:
    from app.communication import InMemoryRunStore, RunEventBus

    org_id = uuid4()
    bus = RunEventBus(store=InMemoryRunStore())

    run = await bus.create_run(
        organization_id=org_id,
        kind="operating",
        request={"mode": "scan"},
    )
    await bus.mark_running(run.run_id, organization_id=org_id)
    await bus.publish(
        run.run_id,
        organization_id=org_id,
        type="agent_plane.planning_started",
        stage="agent_plane",
        message="Planning analyses",
        progress=0.25,
    )
    await bus.complete_run(
        run.run_id,
        organization_id=org_id,
        status="completed",
        result={"status": "completed"},
    )

    stored = await bus.get_run(run.run_id, organization_id=org_id)
    events = await bus.list_events(run.run_id, organization_id=org_id)
    streamed = [
        event.type
        async for event in bus.stream_events(run.run_id, organization_id=org_id)
    ]

    assert stored.status == "completed"
    assert stored.result == {"status": "completed"}
    assert [event.type for event in events] == [
        "run.queued",
        "run.started",
        "agent_plane.planning_started",
        "run.completed",
    ]
    assert streamed == [event.type for event in events]


@pytest.mark.asyncio
async def test_run_event_bus_enforces_organization_boundary() -> None:
    from app.communication import InMemoryRunStore, RunEventBus
    from app.core.errors import NotFoundError

    bus = RunEventBus(store=InMemoryRunStore())
    run = await bus.create_run(
        organization_id=uuid4(),
        kind="operating",
        request={},
    )

    with pytest.raises(NotFoundError):
        await bus.get_run(run.run_id, organization_id=uuid4())

    with pytest.raises(NotFoundError):
        await bus.publish(
            run.run_id,
            organization_id=uuid4(),
            type="run.started",
            stage="run",
            message="Wrong org",
        )
