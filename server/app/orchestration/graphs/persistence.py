"""Postgres-backed persistence adapter for `pydantic_graph`."""

from __future__ import annotations

import copy
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from typing import TYPE_CHECKING, Any

from pydantic_graph import BaseNode, End
from pydantic_graph import exceptions as graph_exceptions
from pydantic_graph.persistence import (
    BaseStatePersistence,
    EndSnapshot,
    NodeSnapshot,
    Snapshot,
    build_snapshot_list_type_adapter,
)
from sqlalchemy import select

from app.db.models.workspace_build import (
    WorkspaceBuildSnapshot,
    WorkspaceBuildSnapshotStatus,
)
from app.db.session import open_session
from app.repositories.workspace_builds import WorkspaceBuildRepository

if TYPE_CHECKING:
    from uuid import UUID

SessionFactory = Callable[[], Any]


class PostgresGraphPersistence[StateT, RunEndT](BaseStatePersistence[StateT, RunEndT]):
    """Stores every pydantic-graph snapshot in `workspace_build_snapshots`.

    The adapter writes on each node boundary, so a failed worker leaves behind
    the exact state and next node that failed. `iter_from_persistence` can later
    resume from the next `created` snapshot with the same state/run-end types.
    """

    def __init__(
        self,
        *,
        build_id: UUID,
        session_factory: SessionFactory = open_session,
        deep_copy: bool = True,
    ) -> None:
        self._build_id = build_id
        self._session_factory = session_factory
        self._deep_copy = deep_copy
        self._snapshots_type_adapter: Any | None = None

    def should_set_types(self) -> bool:
        return self._snapshots_type_adapter is None

    def set_types(self, state_type: type[StateT], run_end_type: type[RunEndT]) -> None:
        self._snapshots_type_adapter = build_snapshot_list_type_adapter(
            state_type,
            run_end_type,
        )

    async def snapshot_node(
        self,
        state: StateT,
        next_node: BaseNode[StateT, Any, RunEndT],
    ) -> None:
        snapshot = NodeSnapshot(
            state=self._prep_state(state),
            node=next_node.deep_copy() if self._deep_copy else next_node,
        )
        await self._append_snapshot(snapshot)

    async def snapshot_node_if_new(
        self,
        snapshot_id: str,
        state: StateT,
        next_node: BaseNode[StateT, Any, RunEndT],
    ) -> None:
        async with self._session_factory() as session:
            repo = WorkspaceBuildRepository(session)
            existing = await repo.get_snapshot(
                build_id=self._build_id,
                snapshot_id=snapshot_id,
            )
            if existing is not None:
                return

        snapshot = NodeSnapshot(
            id=snapshot_id,
            state=self._prep_state(state),
            node=next_node.deep_copy() if self._deep_copy else next_node,
        )
        await self._append_snapshot(snapshot)

    async def snapshot_end(self, state: StateT, end: End[RunEndT]) -> None:
        snapshot = EndSnapshot(
            state=self._prep_state(state),
            result=end.deep_copy_data() if self._deep_copy else end,
        )
        await self._append_snapshot(snapshot)

    @asynccontextmanager
    async def record_run(self, snapshot_id: str) -> AsyncIterator[None]:
        async with self._session_factory() as session:
            repo = WorkspaceBuildRepository(session)
            snapshot = await repo.get_snapshot(
                build_id=self._build_id,
                snapshot_id=snapshot_id,
            )
            if snapshot is None:
                raise LookupError(f"No snapshot found with id={snapshot_id!r}")
            graph_exceptions.GraphNodeStatusError.check(snapshot.status)
            await repo.update_snapshot_status(
                build_id=self._build_id,
                snapshot_id=snapshot_id,
                status=WorkspaceBuildSnapshotStatus.RUNNING,
            )

        started = perf_counter()
        try:
            yield
        except Exception as exc:
            duration_ms = int((perf_counter() - started) * 1000)
            async with self._session_factory() as session:
                repo = WorkspaceBuildRepository(session)
                await repo.update_snapshot_status(
                    build_id=self._build_id,
                    snapshot_id=snapshot_id,
                    status=WorkspaceBuildSnapshotStatus.ERROR,
                    duration_ms=duration_ms,
                    error={"type": type(exc).__name__, "message": str(exc)},
                )
            raise
        else:
            duration_ms = int((perf_counter() - started) * 1000)
            async with self._session_factory() as session:
                repo = WorkspaceBuildRepository(session)
                await repo.update_snapshot_status(
                    build_id=self._build_id,
                    snapshot_id=snapshot_id,
                    status=WorkspaceBuildSnapshotStatus.SUCCESS,
                    duration_ms=duration_ms,
                )

    async def load_next(self) -> NodeSnapshot[StateT, RunEndT] | None:
        async with self._session_factory() as session:
            repo = WorkspaceBuildRepository(session)
            row = await repo.load_next_created(build_id=self._build_id)
            if row is None:
                return None
            await repo.update_snapshot_status(
                build_id=self._build_id,
                snapshot_id=row.snapshot_id,
                status=WorkspaceBuildSnapshotStatus.PENDING,
            )
            payload = row.payload

        snapshot = self._load_snapshot(payload)
        if not isinstance(snapshot, NodeSnapshot):
            raise TypeError(f"Expected NodeSnapshot, got {type(snapshot).__name__}.")
        snapshot.status = WorkspaceBuildSnapshotStatus.PENDING.value
        return snapshot

    async def load_all(self) -> list[Snapshot[StateT, RunEndT]]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(WorkspaceBuildSnapshot)
                    .where(WorkspaceBuildSnapshot.build_id == self._build_id)
                    .order_by(WorkspaceBuildSnapshot.ordinal.asc())
                )
            ).scalars().all()
        return [self._load_snapshot(row.payload) for row in rows]

    async def _append_snapshot(self, snapshot: Snapshot[StateT, RunEndT]) -> None:
        payload = self._dump_snapshot(snapshot)
        node_name = _snapshot_node_name(snapshot)
        async with self._session_factory() as session:
            repo = WorkspaceBuildRepository(session)
            await repo.append_snapshot(
                build_id=self._build_id,
                snapshot_id=snapshot.id,
                kind=snapshot.kind,
                node_name=node_name,
                status=getattr(snapshot, "status", WorkspaceBuildSnapshotStatus.SUCCESS.value),
                payload=payload,
            )

    def _dump_snapshot(self, snapshot: Snapshot[StateT, RunEndT]) -> dict[str, Any]:
        if self._snapshots_type_adapter is None:
            raise AssertionError("type adapter must be set before dumping graph snapshots")
        payload = self._snapshots_type_adapter.dump_python([snapshot], mode="json")[0]
        if not isinstance(payload, dict):
            raise TypeError("Snapshot payload did not serialize to a JSON object.")
        return payload

    def _load_snapshot(self, payload: dict[str, Any]) -> Snapshot[StateT, RunEndT]:
        if self._snapshots_type_adapter is None:
            raise AssertionError("type adapter must be set before loading graph snapshots")
        return self._snapshots_type_adapter.validate_python([payload])[0]

    def _prep_state(self, state: StateT) -> StateT:
        if not self._deep_copy or state is None:
            return state
        return copy.deepcopy(state)


def _snapshot_node_name(snapshot: Snapshot[Any, Any]) -> str:
    node = snapshot.node
    if isinstance(node, End):
        return "End"
    return node.get_node_id()
