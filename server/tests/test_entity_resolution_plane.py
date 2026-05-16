from __future__ import annotations


def test_entity_resolution_plans_are_extracted_from_surface_candidates() -> None:
    from app.business_surface_plane import mine_business_surfaces
    from app.entity_resolution_plane import plan_entity_resolution_from_surfaces
    from tests.test_business_surface_plane import _receivables_run

    surfaces = mine_business_surfaces(_receivables_run())
    result = plan_entity_resolution_from_surfaces(surfaces)

    assert result.plans
    plan = result.plans[0]
    assert plan.engine == "splink"
    assert plan.link_type == "link_only"
    assert plan.blocking_fields
    assert result.executions[0].status == "planned"


def test_entity_resolution_execute_delegates_to_engine() -> None:
    from app.entity_resolution_plane import EntityResolutionExecution, execute_entity_resolution
    from app.entity_resolution_plane.contracts import EntityResolutionDataset, EntityResolutionPlan

    class FakeEngine:
        def run(self, plan, datasets, *, max_pairs=500):
            return EntityResolutionExecution(
                plan_id=plan.plan_id,
                status="completed",
                row_count=len(datasets),
            )

    plan = EntityResolutionPlan(
        plan_id="er:test",
        surface_id="receivables",
        view_id="receivables:entity_resolution:party",
        entity="party",
        link_type="link_only",
        fields=[],
        why="Match parties.",
    )
    dataset = EntityResolutionDataset(dataset_id="a", label="A", rows=[], field_map={})

    execution = execute_entity_resolution(plan, [dataset], engine=FakeEngine())

    assert execution.status == "completed"
    assert execution.row_count == 1


async def test_entity_resolution_runner_loads_datasets_and_executes(monkeypatch) -> None:
    from uuid import uuid4

    from app.business_surface_plane import mine_business_surfaces
    from app.entity_resolution_plane.contracts import (
        EntityResolutionDataset,
        EntityResolutionExecution,
    )
    from app.entity_resolution_plane.service import run_entity_resolution_from_surfaces
    from tests.test_business_surface_plane import _receivables_run

    async def fake_datasets_for_plan(organization_id, plan, *, max_rows_per_dataset):
        _ = (organization_id, max_rows_per_dataset)
        return [
            EntityResolutionDataset(
                dataset_id="bill_detail",
                label="Bill Detail",
                rows=[{"bf_record_id": "1", "party_name": "Acme"}],
                field_map={field.field_id: field.field_id for field in plan.fields},
            )
        ]

    class FakeEngine:
        def run(self, plan, datasets, *, max_pairs=500):
            return EntityResolutionExecution(
                plan_id=plan.plan_id,
                status="completed",
                row_count=sum(len(dataset.rows) for dataset in datasets),
                matches=[
                    {
                        "left_dataset_id": "bill_detail",
                        "left_record_id": "1",
                        "right_dataset_id": "bill_detail",
                        "right_record_id": "1",
                        "match_probability": 0.99,
                    }
                ],
            )

    monkeypatch.setattr(
        "app.entity_resolution_plane.service._datasets_for_plan",
        fake_datasets_for_plan,
    )

    surfaces = mine_business_surfaces(_receivables_run())
    result = await run_entity_resolution_from_surfaces(uuid4(), surfaces, engine=FakeEngine())

    assert result.executions
    assert result.executions[0].status == "completed"
    assert result.executions[0].row_count == 1
