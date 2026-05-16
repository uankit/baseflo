"""Runtime validation helpers for already-planned execution nodes."""

from __future__ import annotations

from app.execution_plane.contracts import ExecutionCatalog, NodeState, PlanValidationError


def require_input(states: dict[str, NodeState], input_id: str, *, op_id: str) -> NodeState:
    state = states.get(input_id)
    if state is None:
        raise PlanValidationError(
            "Operator references an input that has not been built",
            details={"operator_id": op_id, "input": input_id},
        )
    return state


def require_field(state: NodeState, field_id: str, *, op_id: str) -> None:
    if field_id not in state.fields:
        raise PlanValidationError(
            "Field is not available on operator input",
            details={"operator_id": op_id, "field_id": field_id},
        )


def require_relationship(
    catalog: ExecutionCatalog,
    left_field_id: str,
    right_field_id: str,
    *,
    op_id: str,
) -> None:
    if not catalog.relationship_allowed(left_field_id, right_field_id):
        raise PlanValidationError(
            "Join fields do not have relationship evidence",
            details={
                "operator_id": op_id,
                "left_field_id": left_field_id,
                "right_field_id": right_field_id,
            },
        )
