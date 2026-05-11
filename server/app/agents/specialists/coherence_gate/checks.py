"""Deterministic structural checks for CoherenceGate.

The orchestrator calls these BEFORE the agent runs, then feeds the results
as `deterministic_findings`. The agent reads them as facts (per the
Evidence-Feeding pattern from docs/50-design-patterns.md §8B) and decides
severity + repair routing.

These checks are pure functions over typed inputs; they NEVER fix anything.
"""

from __future__ import annotations

from app.agents.specialists.cardinality_resolver.types import CardinalityDecision
from app.agents.specialists.coherence_gate.types import (
    CoherenceGateOutput,
    CoherenceReport,
    CrossCuttingIssue,
    DeterministicFinding,
    FindingCategory,
    IssueCategory,
    IssueSeverity,
)
from app.agents.specialists.kpi_planner.types import (
    ColumnRef,
    FilterOp,
    KPIDefinition,
    KPIFormula,
)
from app.engines.schema.enums import (
    PII_SEMANTIC_TYPES,
    PhysicalType,
    SemanticType,
)
from app.engines.schema.ir import SchemaIR


def _walk_kpi_refs(formula: KPIFormula) -> list[ColumnRef]:
    refs: list[ColumnRef] = []
    if formula.column is not None:
        refs.append(formula.column)
    if formula.numerator is not None:
        refs.extend(_walk_kpi_refs(formula.numerator))
    if formula.denominator is not None:
        refs.extend(_walk_kpi_refs(formula.denominator))
    return refs


def check_kpi_columns_exist(
    ir: SchemaIR, kpis: list[KPIDefinition]
) -> list[DeterministicFinding]:
    """Every KPI's referenced columns must exist in the IR."""
    findings: list[DeterministicFinding] = []
    table_columns: dict[str, set[str]] = {
        t.name: {c.name for c in t.columns} for t in ir.tables
    }
    for kpi in kpis:
        refs = _walk_kpi_refs(kpi.formula)
        if kpi.time_dimension is not None:
            refs.append(kpi.time_dimension)
        if kpi.breakdown_dimension is not None:
            refs.append(kpi.breakdown_dimension)
        for f in kpi.filters:
            refs.append(f.column)

        for ref in refs:
            if ref.table not in table_columns:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.KPI_COLUMN_MISSING,
                        description=(
                            f"KPI {kpi.name!r} references unknown table {ref.table!r}."
                        ),
                        affected_artifacts=[f"kpi:{kpi.name}", f"table:{ref.table}"],
                    )
                )
                continue
            if ref.column not in table_columns[ref.table]:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.KPI_COLUMN_MISSING,
                        description=(
                            f"KPI {kpi.name!r} references missing column "
                            f"{ref.table}.{ref.column}."
                        ),
                        affected_artifacts=[
                            f"kpi:{kpi.name}",
                            f"column:{ref.table}.{ref.column}",
                        ],
                    )
                )
    return findings


def check_relationship_endpoints_exist(ir: SchemaIR) -> list[DeterministicFinding]:
    table_names = {t.name for t in ir.tables}
    findings: list[DeterministicFinding] = []
    for rel in ir.relationships:
        if rel.from_table not in table_names:
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.RELATIONSHIP_ENDPOINT_MISSING,
                    description=(
                        f"Relationship {rel.name!r} from_table {rel.from_table!r} "
                        "is missing from the schema."
                    ),
                    affected_artifacts=[f"relationship:{rel.name}"],
                )
            )
        if rel.to_table not in table_names:
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.RELATIONSHIP_ENDPOINT_MISSING,
                    description=(
                        f"Relationship {rel.name!r} to_table {rel.to_table!r} "
                        "is missing from the schema."
                    ),
                    affected_artifacts=[f"relationship:{rel.name}"],
                )
            )
    return findings


def check_cardinality_consistency(
    ir: SchemaIR, cardinalities: list[CardinalityDecision]
) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []
    relationship_index = {
        (
            rel.from_table,
            tuple(rel.from_columns),
            rel.to_table,
            tuple(rel.to_columns),
        ): rel
        for rel in ir.relationships
    }
    for decision in cardinalities:
        rel = relationship_index.get(
            (
                decision.from_table,
                tuple(decision.from_columns),
                decision.to_table,
                tuple(decision.to_columns),
            )
        )
        if rel is None:
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.RELATIONSHIP_MISSING,
                    description=(
                        f"Cardinality decision {decision.relationship_name!r} has "
                        "no matching SchemaIR relationship."
                    ),
                    affected_artifacts=[f"relationship:{decision.relationship_name}"],
                )
            )
            continue
        if decision.cardinality != rel.cardinality:
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.CARDINALITY_INCONSISTENT,
                    description=(
                        f"Relationship {rel.name!r} cardinality "
                        f"{rel.cardinality.value!r} disagrees with "
                        f"CardinalityResolver decision {decision.cardinality.value!r}."
                    ),
                    affected_artifacts=[f"relationship:{rel.name}"],
                )
            )

    decision_index = {(d.from_table, d.to_table): d for d in cardinalities}
    for rel in ir.relationships:
        decision = decision_index.get((rel.from_table, rel.to_table))
        if decision is None:
            continue
        if decision.cardinality != rel.cardinality:
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.CARDINALITY_INCONSISTENT,
                    description=(
                        f"Relationship {rel.name!r} cardinality "
                        f"{rel.cardinality.value!r} disagrees with "
                        f"CardinalityResolver decision {decision.cardinality.value!r}."
                    ),
                    affected_artifacts=[f"relationship:{rel.name}"],
                )
            )
    return findings


def check_kpi_time_dimensions_temporal(
    ir: SchemaIR, kpis: list[KPIDefinition]
) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []
    columns = {
        (table.name, column.name): column
        for table in ir.tables
        for column in table.columns
    }
    temporal_physical = {PhysicalType.DATE, PhysicalType.TIMESTAMPTZ}
    for kpi in kpis:
        if kpi.time_dimension is None:
            continue
        column = columns.get((kpi.time_dimension.table, kpi.time_dimension.column))
        if column is None:
            continue
        if (
            column.semantic_type != SemanticType.TEMPORAL
            or column.physical_type not in temporal_physical
        ):
            findings.append(
                DeterministicFinding(
                    category=FindingCategory.KPI_TIME_DIMENSION_INVALID,
                    description=(
                        f"KPI {kpi.name!r} uses {kpi.time_dimension.table}."
                        f"{kpi.time_dimension.column} as a time_dimension, but "
                        f"that column is {column.semantic_type.value}/"
                        f"{column.physical_type.value}."
                    ),
                    affected_artifacts=[
                        f"kpi:{kpi.name}",
                        f"column:{kpi.time_dimension.table}.{kpi.time_dimension.column}",
                    ],
                )
            )
    return findings


def check_kpi_status_filters_valid(
    ir: SchemaIR, kpis: list[KPIDefinition]
) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []
    status_enums = {
        (table.name, column.name): set(column.enum_values or [])
        for table in ir.tables
        for column in table.columns
        if column.semantic_type == SemanticType.STATUS
    }
    for kpi in kpis:
        for kpi_filter in kpi.filters:
            allowed = status_enums.get(
                (kpi_filter.column.table, kpi_filter.column.column)
            )
            if allowed is None:
                continue
            if kpi_filter.op in {FilterOp.IS_NULL, FilterOp.IS_NOT_NULL}:
                continue
            values = (
                [str(value) for value in kpi_filter.value]
                if isinstance(kpi_filter.value, list)
                else ([] if kpi_filter.value is None else [str(kpi_filter.value)])
            )
            unknown = [value for value in values if value not in allowed]
            if unknown:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.KPI_STATUS_FILTER_INVALID,
                        description=(
                            f"KPI {kpi.name!r} filters status column "
                            f"{kpi_filter.column.table}.{kpi_filter.column.column} "
                            f"by unknown enum values {unknown!r}; allowed values "
                            f"are {sorted(allowed)!r}."
                        ),
                        affected_artifacts=[
                            f"kpi:{kpi.name}",
                            f"column:{kpi_filter.column.table}.{kpi_filter.column.column}",
                        ],
                    )
                )
    return findings


def check_pii_masking(ir: SchemaIR) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []
    for table in ir.tables:
        for col in table.columns:
            if col.semantic_type in PII_SEMANTIC_TYPES and not col.pii_masked_by_default:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.PII_NOT_MASKED,
                        description=(
                            f"PII column {table.name}.{col.name} "
                            f"({col.semantic_type.value}) must have "
                            "pii_masked_by_default=True."
                        ),
                        affected_artifacts=[f"column:{table.name}.{col.name}"],
                    )
                )
    return findings


def check_money_shape(ir: SchemaIR) -> list[DeterministicFinding]:
    findings: list[DeterministicFinding] = []
    for table in ir.tables:
        for col in table.columns:
            if col.semantic_type != SemanticType.MONEY:
                continue
            if col.physical_type != PhysicalType.BIGINT:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.MONEY_SHAPE_INVALID,
                        description=(
                            f"Money column {table.name}.{col.name} must be BIGINT "
                            f"minor-unit; got {col.physical_type.value}."
                        ),
                        affected_artifacts=[f"column:{table.name}.{col.name}"],
                    )
                )
            if not col.is_minor_unit:
                findings.append(
                    DeterministicFinding(
                        category=FindingCategory.MONEY_SHAPE_INVALID,
                        description=(
                            f"Money column {table.name}.{col.name} missing "
                            "is_minor_unit=True."
                        ),
                        affected_artifacts=[f"column:{table.name}.{col.name}"],
                    )
                )
    return findings


def compute_findings(
    *,
    ir: SchemaIR,
    kpis: list[KPIDefinition],
    cardinalities: list[CardinalityDecision],
) -> list[DeterministicFinding]:
    """Run every check and concatenate findings in deterministic order."""
    findings: list[DeterministicFinding] = []
    if not ir.tables:
        return [
            DeterministicFinding(
                category=FindingCategory.EMPTY_SCHEMA,
                description="SchemaIR has no tables.",
                affected_artifacts=["schema"],
            )
        ]
    findings.extend(check_relationship_endpoints_exist(ir))
    findings.extend(check_cardinality_consistency(ir, cardinalities))
    findings.extend(check_pii_masking(ir))
    findings.extend(check_money_shape(ir))
    findings.extend(check_kpi_columns_exist(ir, kpis))
    findings.extend(check_kpi_time_dimensions_temporal(ir, kpis))
    findings.extend(check_kpi_status_filters_valid(ir, kpis))
    return findings


def build_coherence_output(
    findings: list[DeterministicFinding],
) -> CoherenceGateOutput:
    """Compile deterministic findings into the terminal coherence report.

    Coherence is not an LLM repair loop. If structural compiler checks are
    clean, the workspace ships. If they are not, the build fails once with
    precise issues; upstream deterministic validators should prevent this in
    normal operation.
    """
    if not findings:
        return CoherenceGateOutput(
            report=CoherenceReport(
                passed=True,
                issues=[],
                repair_routes=[],
                escalate_to_user=None,
                rationale="No deterministic structural findings.",
            )
        )

    issues = [
        CrossCuttingIssue(
            severity=IssueSeverity.BLOCKING,
            category=_issue_category_for_finding(finding.category),
            description=finding.description,
            affected_artifacts=finding.affected_artifacts,
        )
        for finding in findings
    ]
    return CoherenceGateOutput(
        report=CoherenceReport.model_construct(
            passed=False,
            issues=issues,
            repair_routes=[],
            escalate_to_user=None,
            rationale="Deterministic coherence checks found structural blockers.",
        )
    )


def _issue_category_for_finding(category: FindingCategory) -> IssueCategory:
    if category == FindingCategory.KPI_COLUMN_MISSING:
        return IssueCategory.KPI_COLUMN_MISSING
    if category == FindingCategory.CARDINALITY_INCONSISTENT:
        return IssueCategory.CARDINALITY_INCONSISTENT
    if category in {
        FindingCategory.PII_NOT_MASKED,
    }:
        return IssueCategory.PII_PROPAGATION
    if category == FindingCategory.MONEY_SHAPE_INVALID:
        return IssueCategory.MONEY_SHAPE
    return IssueCategory.OTHER
