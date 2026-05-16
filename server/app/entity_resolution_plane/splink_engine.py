"""Splink adapter for Baseflo entity-resolution plans."""

from __future__ import annotations

from typing import Any

from app.entity_resolution_plane.contracts import (
    EntityMatch,
    EntityResolutionDataset,
    EntityResolutionExecution,
    EntityResolutionPlan,
)


class SplinkDependencyError(RuntimeError):
    """Raised when the Splink runtime dependency is unavailable."""


class SplinkEntityResolutionEngine:
    """Execute entity-resolution plans with Splink's DuckDB backend.

    The adapter keeps Splink behind Baseflo contracts. The rest of the backend
    never depends on Splink settings dictionaries, Pandas dataframes, or linker
    result objects.
    """

    def run(
        self,
        plan: EntityResolutionPlan,
        datasets: list[EntityResolutionDataset],
        *,
        max_pairs: int = 500,
    ) -> EntityResolutionExecution:
        if not datasets:
            return EntityResolutionExecution(
                plan_id=plan.plan_id,
                status="failed",
                error="No datasets supplied for entity resolution.",
            )
        try:
            pd, splink, cl = _import_splink_runtime()
            settings = _settings(plan, cl, splink.block_on)
            dataframes = [_dataframe(pd, dataset) for dataset in datasets]
            db_api = splink.DuckDBAPI()
            linker = splink.Linker(
                dataframes[0] if len(dataframes) == 1 else dataframes,
                settings,
                db_api,
                input_table_aliases=[dataset.dataset_id for dataset in datasets]
                if len(datasets) > 1
                else None,
            )
            predictions = linker.inference.predict(
                threshold_match_probability=plan.threshold_match_probability
            )
            rows = predictions.as_pandas_dataframe(limit=max_pairs).to_dict("records")
            matches = [_match(row, datasets) for row in rows]
            clusters = []
            try:
                clustered = linker.clustering.cluster_pairwise_predictions_at_threshold(
                    predictions,
                    plan.threshold_match_probability,
                )
                clusters = _clusters(clustered.as_pandas_dataframe(limit=max_pairs).to_dict("records"))
            except Exception:
                clusters = []
            return EntityResolutionExecution(
                plan_id=plan.plan_id,
                status="completed",
                matches=matches,
                clusters=clusters,
                row_count=len(matches),
            )
        except SplinkDependencyError:
            raise
        except Exception as exc:
            return EntityResolutionExecution(
                plan_id=plan.plan_id,
                status="failed",
                error=str(exc),
            )


def _import_splink_runtime() -> tuple[Any, Any, Any]:
    try:
        import pandas as pd  # type: ignore[import-untyped]
        import splink
        import splink.comparison_library as cl
    except ImportError as exc:
        raise SplinkDependencyError(
            "Splink entity resolution requires the 'splink' and 'pandas' packages."
        ) from exc
    return pd, splink, cl


def _settings(plan: EntityResolutionPlan, cl: Any, block_on: Any) -> Any:
    comparisons = [_comparison(field, cl) for field in plan.fields]
    blocking = [
        block_on(_canonical_column(field_id))
        for field_id in plan.blocking_fields
        if _canonical_column(field_id)
    ]
    if not blocking:
        first_name_like = next(
            (field for field in plan.fields if field.role in {"name", "identifier", "email"}),
            None,
        )
        if first_name_like is not None:
            blocking = [block_on(_canonical_column(first_name_like.field_id))]
    return _splink_settings_creator()(
        link_type=plan.link_type,
        unique_id_column_name="bf_record_id",
        source_dataset_column_name="bf_dataset",
        comparisons=comparisons,
        blocking_rules_to_generate_predictions=blocking,
    )


def _splink_settings_creator() -> Any:
    try:
        from splink import SettingsCreator
    except ImportError as exc:
        raise SplinkDependencyError("Splink SettingsCreator is unavailable.") from exc
    return SettingsCreator


def _comparison(field: Any, cl: Any) -> Any:
    column = _canonical_column(field.field_id)
    if field.role == "email":
        return cl.EmailComparison(column)
    if field.role == "phone":
        return cl.ExactMatch(column)
    if field.role == "identifier":
        return cl.ExactMatch(column).configure(term_frequency_adjustments=True)
    if field.role == "name":
        return cl.JaroWinklerAtThresholds(column, [0.95, 0.88, 0.75])
    return cl.ExactMatch(column)


def _dataframe(pd: Any, dataset: EntityResolutionDataset) -> Any:
    rows: list[dict[str, Any]] = []
    for index, raw in enumerate(dataset.rows):
        row: dict[str, Any] = {
            "bf_record_id": str(raw.get("bf_record_id") or raw.get("_bf_record_id") or index),
            "bf_dataset": dataset.dataset_id,
        }
        for field_id, source_key in dataset.field_map.items():
            row[_canonical_column(field_id)] = raw.get(source_key)
        rows.append(row)
    return pd.DataFrame(rows)


def _match(row: dict[str, Any], datasets: list[EntityResolutionDataset]) -> EntityMatch:
    left_record_id: str = _text(row.get("bf_record_id_l"), _text(row.get("unique_id_l")))
    right_record_id: str = _text(row.get("bf_record_id_r"), _text(row.get("unique_id_r")))
    return EntityMatch(
        left_dataset_id=_text(row.get("bf_dataset_l")) or _text(row.get("source_dataset_l")) or None,
        left_record_id=left_record_id,
        right_dataset_id=_text(row.get("bf_dataset_r")) or _text(row.get("source_dataset_r")) or None,
        right_record_id=right_record_id,
        match_probability=_probability(row),
        match_weight=_float_or_none(row.get("match_weight")),
        evidence={
            key: value
            for key, value in row.items()
            if key not in {"bf_record_id_l", "bf_record_id_r", "match_probability", "match_weight"}
        },
    )


def _clusters(rows: list[dict[str, Any]]) -> list[Any]:
    from app.entity_resolution_plane.contracts import EntityCluster

    clusters: dict[str, list[str]] = {}
    probabilities: dict[str, list[float]] = {}
    for row in rows:
        cluster_id = _text(row.get("cluster_id"))
        if not cluster_id:
            continue
        record_id = _text(row.get("bf_record_id"), _text(row.get("unique_id")))
        if record_id:
            clusters.setdefault(cluster_id, []).append(record_id)
        probability = _float_or_none(row.get("match_probability"))
        if probability is not None:
            probabilities.setdefault(cluster_id, []).append(probability)
    return [
        EntityCluster(
            cluster_id=cluster_id,
            record_refs=sorted(set(records)),
            confidence=round(
                sum(probabilities.get(cluster_id, [0.5])) / len(probabilities.get(cluster_id, [0.5])),
                3,
            ),
        )
        for cluster_id, records in clusters.items()
    ]


def _canonical_column(field_id: str) -> str:
    return field_id.replace(".", "__").replace("-", "_").replace(" ", "_").lower()


def _probability(row: dict[str, Any]) -> float:
    value = _float_or_none(row.get("match_probability"))
    if value is None:
        return 0.5
    return max(0.0, min(1.0, value))


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback
