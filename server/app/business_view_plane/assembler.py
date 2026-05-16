"""Build a source-neutral Business View from an operating run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.business_view_plane.contracts import (
    BusinessEntityView,
    BusinessViewDrilldown,
    BusinessViewMetric,
    BusinessViewPackage,
    BusinessViewSection,
    BusinessViewSectionKind,
)


@dataclass(frozen=True, slots=True)
class _SectionSpec:
    kind: BusinessViewSectionKind
    title: str
    description: str
    terms: tuple[str, ...]
    asset_terms: tuple[str, ...]
    questions: tuple[str, ...]


_SECTION_SPECS = (
    _SectionSpec(
        kind="sales",
        title="Sales",
        description="Revenue movement, selling activity, and buyer momentum.",
        terms=("sale", "sales", "revenue", "order", "bill", "invoice", "amount", "customer"),
        asset_terms=("revenue_event", "order", "bill", "invoice", "sales"),
        questions=(
            "Who is selling or buying the most?",
            "Which parties have dropped versus their usual pattern?",
            "Show sales by party, item, and time period.",
        ),
    ),
    _SectionSpec(
        kind="receivables",
        title="Receivables",
        description="Pending amounts, balances, dues, and parties to follow up with.",
        terms=("pending", "balance", "due", "outstanding", "receivable", "party", "bill"),
        asset_terms=("ledger", "receivable", "bill", "invoice"),
        questions=(
            "Which parties have the highest pending amount?",
            "Which pending bills look overdue or unusual?",
            "Compare bill amount versus pending amount by party.",
        ),
    ),
    _SectionSpec(
        kind="inventory",
        title="Inventory",
        description="Stock, quantities, movement, low cover, and slow-moving items.",
        terms=("inventory", "stock", "qty", "quantity", "item", "sku", "product", "grout"),
        asset_terms=("inventory", "capacity", "stock", "product"),
        questions=(
            "Which items are moving fastest and slowest?",
            "Which products look understocked or overstocked?",
            "Compare item quantity against recent sales or billing.",
        ),
    ),
    _SectionSpec(
        kind="customers_parties",
        title="Customers & Parties",
        description="Named business relationships, buyers, vendors, and accounts.",
        terms=("customer", "party", "vendor", "supplier", "account", "name", "phone", "email"),
        asset_terms=("entity", "customer", "party", "vendor", "audience"),
        questions=(
            "Which parties deserve attention today?",
            "Which customers are growing or shrinking?",
            "Show each party with sales, pending amount, and recent activity.",
        ),
    ),
    _SectionSpec(
        kind="products_items",
        title="Products & Items",
        description="Products, SKUs, item families, and product-level performance.",
        terms=("product", "item", "sku", "style", "variant", "category", "article"),
        asset_terms=("product", "sku", "catalog", "item"),
        questions=(
            "Which products are selling and which are not?",
            "Which products have demand but weak inventory?",
            "Compare product performance across parties or channels.",
        ),
    ),
    _SectionSpec(
        kind="expenses",
        title="Expenses",
        description="Costs, spends, expense heads, and outflow patterns.",
        terms=("expense", "cost", "spend", "paid", "payment", "debit"),
        asset_terms=("spend_event", "expense", "ledger", "cost"),
        questions=(
            "Which expense heads changed the most?",
            "Where is cost concentrated?",
            "Compare expenses against sales for the same period.",
        ),
    ),
    _SectionSpec(
        kind="operations",
        title="Operations",
        description="Fulfillment, returns, process status, and operational exceptions.",
        terms=("status", "return", "fulfillment", "delivery", "task", "process", "operation"),
        asset_terms=("return", "task", "support_event", "fulfillment", "operations"),
        questions=(
            "Which operational statuses need attention?",
            "What changed in returns, delays, or completion status?",
            "Which process exceptions repeat most often?",
        ),
    ),
)

_REVENUE_TERMS = ("sale", "sales", "revenue", "order", "bill", "invoice", "credit")
_COST_TERMS = ("expense", "cost", "spend", "paid", "payment", "debit", "purchase")


def assemble_business_view(run: Any) -> BusinessViewPackage:
    run_data = _dump(run)
    business_model = _record(run_data.get("business_model"))
    field_roles = _record_list(run_data.get("field_roles"))
    asset_roles = _record_list(run_data.get("asset_roles"))
    executions = _record_list(run_data.get("executions"))
    patterns = _record(run_data.get("patterns"))
    context = _record(run_data.get("context_summary"))

    sections = _sections(
        field_roles=field_roles,
        asset_roles=asset_roles,
        executions=executions,
        patterns=patterns,
        context=context,
    )
    if not sections:
        sections = [_connected_data_section(asset_roles, field_roles, executions, context)]

    entity_views = _entity_views(
        business_model=business_model,
        asset_roles=asset_roles,
        field_roles=field_roles,
        executions=executions,
    )

    headline = _headline(business_model, sections)
    summary = (
        f"Baseflo generated {len(sections)} operating views from "
        f"{context.get('asset_count', len(asset_roles))} assets and "
        f"{context.get('row_count', 0)} rows."
    )
    return BusinessViewPackage(
        headline=headline,
        summary=summary,
        why=(
            "This view is generated from semantic asset roles, field roles, "
            "business graph nodes, and materialized execution evidence."
        ),
        sections=sections,
        entity_views=entity_views,
        generated_from={
            "asset_count": context.get("asset_count", len(asset_roles)),
            "field_count": context.get("field_count", len(field_roles)),
            "row_count": context.get("row_count", 0),
            "execution_count": len(executions),
        },
        confidence=_confidence(sections),
    )


def _sections(
    *,
    field_roles: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
    context: dict[str, Any],
) -> list[BusinessViewSection]:
    sections: list[BusinessViewSection] = []
    for spec in _SECTION_SPECS:
        fields = _matching_fields(field_roles, spec.terms)
        assets = _matching_assets(asset_roles, spec.asset_terms + spec.terms)
        graphs = _matching_graphs(executions, patterns, spec.terms + spec.asset_terms)
        if not fields and not assets and not graphs:
            continue
        sections.append(_section(spec, fields, assets, graphs))

    profit_loss = _profit_loss_section(field_roles, asset_roles, executions, patterns)
    if profit_loss is not None:
        sections.append(profit_loss)

    sections.append(_data_quality_section(context, executions))
    return _dedupe_sections(sections)


def _section(
    spec: _SectionSpec,
    fields: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> BusinessViewSection:
    field_refs = _unique(_text(field.get("field_id")) for field in fields)
    asset_ids = _unique(
        [
            *[_text(asset.get("asset_id")) for asset in assets],
            *[_text(field.get("asset_id")) for field in fields],
        ]
    )
    graph_refs = _unique(_text(graph.get("graph_id")) for graph in graphs)
    title = spec.title
    why_built = _why_built(title, fields, assets, graphs)
    metrics = _execution_metrics(graphs)
    return BusinessViewSection(
        section_id=spec.kind,
        kind=spec.kind,
        title=title,
        description=spec.description,
        why_built=why_built,
        confidence=_section_confidence(fields, assets, graphs),
        tags=_unique([spec.kind, title.lower(), *_asset_tags(assets)]),
        metrics=metrics,
        source_asset_ids=asset_ids,
        field_refs=field_refs,
        graph_refs=graph_refs,
        insight_refs=[f"insight:{graph_id}" for graph_id in graph_refs],
        table_refs=[f"table:{graph_id}" for graph_id in graph_refs],
        chart_refs=_chart_refs(graphs),
        action_refs=_action_refs(graphs),
        suggested_questions=list(spec.questions),
        drilldowns=_drilldowns(spec, graph_refs, field_refs),
    )


def _profit_loss_section(
    field_roles: list[dict[str, Any]],
    asset_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
) -> BusinessViewSection | None:
    revenue_fields = _matching_fields(field_roles, _REVENUE_TERMS)
    cost_fields = _matching_fields(field_roles, _COST_TERMS)
    revenue_assets = _matching_assets(asset_roles, _REVENUE_TERMS)
    cost_assets = _matching_assets(asset_roles, _COST_TERMS)
    if not (revenue_fields or revenue_assets) or not (cost_fields or cost_assets):
        return None
    graphs = _matching_graphs(executions, patterns, _REVENUE_TERMS + _COST_TERMS)
    field_refs = _unique(_text(field.get("field_id")) for field in revenue_fields + cost_fields)
    asset_ids = _unique(
        [
            *[_text(asset.get("asset_id")) for asset in revenue_assets + cost_assets],
            *[_text(field.get("asset_id")) for field in revenue_fields + cost_fields],
        ]
    )
    graph_refs = _unique(_text(graph.get("graph_id")) for graph in graphs)
    return BusinessViewSection(
        section_id="profit_loss",
        kind="profit_loss",
        title="Profit & Loss",
        description="Revenue versus cost signals that can become a P&L view.",
        why_built=(
            "Because this data has revenue-like signals "
            f"({_names(revenue_fields, revenue_assets)}) and cost-like signals "
            f"({_names(cost_fields, cost_assets)}), Baseflo can build a P&L view."
        ),
        confidence=0.78 if revenue_fields and cost_fields else 0.64,
        tags=["profit_loss", "revenue", "cost"],
        metrics=_execution_metrics(graphs),
        source_asset_ids=asset_ids,
        field_refs=field_refs,
        graph_refs=graph_refs,
        insight_refs=[f"insight:{graph_id}" for graph_id in graph_refs],
        table_refs=[f"table:{graph_id}" for graph_id in graph_refs],
        chart_refs=_chart_refs(graphs),
        action_refs=_action_refs(graphs),
        suggested_questions=[
            "Build a profit and loss view from revenue and expense fields.",
            "Which expenses are growing faster than sales?",
            "Compare revenue, cost, and pending amount by period.",
        ],
        drilldowns=_drilldowns(
            _SectionSpec(
                kind="profit_loss",
                title="Profit & Loss",
                description="",
                terms=_REVENUE_TERMS + _COST_TERMS,
                asset_terms=(),
                questions=(),
            ),
            graph_refs,
            field_refs,
        ),
    )


def _data_quality_section(
    context: dict[str, Any],
    executions: list[dict[str, Any]],
) -> BusinessViewSection:
    failed = [execution for execution in executions if _text(execution.get("status")) == "failed"]
    completed = [execution for execution in executions if _text(execution.get("status")) == "completed"]
    metrics = [
        BusinessViewMetric(
            label="Connected rows",
            value=str(context.get("row_count", 0)),
            why="Total rows seen in the canonical data plane for this run.",
        ),
        BusinessViewMetric(
            label="Executed analyses",
            value=str(len(completed)),
            why="Materialized analyses available for charts, tables, and evidence.",
        ),
    ]
    if failed:
        metrics.append(
            BusinessViewMetric(
                label="Failed analyses",
                value=str(len(failed)),
                why="Plans that could not be materialized and need source or relationship review.",
            )
        )
    return BusinessViewSection(
        section_id="data_quality",
        kind="data_quality",
        title="Source Health & Coverage",
        description="What Baseflo could read, materialize, and explain from the connected data.",
        why_built="Because every operating view depends on trusted source coverage and executed evidence.",
        confidence=0.9 if not failed else 0.7,
        tags=["data_quality", "source_health"],
        metrics=metrics,
        suggested_questions=[
            "What data is missing to improve the operating view?",
            "Which fields or joins are weak?",
            "What can Baseflo confidently answer from this data?",
        ],
    )


def _connected_data_section(
    asset_roles: list[dict[str, Any]],
    field_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
    context: dict[str, Any],
) -> BusinessViewSection:
    graph_refs = _unique(_text(execution.get("graph_id")) for execution in executions)
    field_refs = _unique(_text(field.get("field_id")) for field in field_roles[:12])
    asset_ids = _unique(_text(asset.get("asset_id")) for asset in asset_roles)
    return BusinessViewSection(
        section_id="connected_data",
        kind="connected_data",
        title="Connected Data",
        description="A neutral view of what Baseflo can currently inspect.",
        why_built=(
            f"Because this workspace has {context.get('asset_count', len(asset_roles))} assets "
            f"and {context.get('row_count', 0)} rows connected."
        ),
        confidence=0.55,
        tags=["connected_data"],
        source_asset_ids=asset_ids,
        field_refs=field_refs,
        graph_refs=graph_refs,
        suggested_questions=[
            "What are the most important fields in this data?",
            "Which business views can Baseflo build from these sources?",
            "What should I connect next?",
        ],
    )


def _entity_views(
    *,
    business_model: dict[str, Any],
    asset_roles: list[dict[str, Any]],
    field_roles: list[dict[str, Any]],
    executions: list[dict[str, Any]],
) -> list[BusinessEntityView]:
    views: list[BusinessEntityView] = []
    for entity in _record_list(business_model.get("entities")):
        name = _text(entity.get("name"))
        if not name:
            continue
        asset_ids = _unique(
            [
                _text(entity.get("primary_asset_id")),
                *_list(entity.get("related_asset_ids")),
                *[
                    _text(asset.get("asset_id"))
                    for asset in asset_roles
                    if _text(asset.get("entity_type")).lower() == name.lower()
                ],
            ]
        )
        fields = [
            field
            for field in field_roles
            if _text(field.get("asset_id")) in set(asset_ids)
            or _text(field.get("entity_hint")).lower() == name.lower()
        ]
        graph_refs = _unique(
            _text(execution.get("graph_id"))
            for execution in executions
            if name.lower() in _search_blob(execution)
        )
        views.append(
            BusinessEntityView(
                entity=name,
                plural=_text(entity.get("plural"), f"{name}s"),
                description=_text(entity.get("description"), f"{name.title()} records."),
                why_available=(
                    f"Because Baseflo found {name} as a business entity in the connected data."
                ),
                source_asset_ids=asset_ids,
                field_refs=_unique(_text(field.get("field_id")) for field in fields),
                graph_refs=graph_refs,
                suggested_questions=[
                    f"Show me {name} performance and exceptions.",
                    f"Which {name} records need attention?",
                    f"Compare {name} by amount, activity, and status.",
                ],
            )
        )
    return views


def _matching_fields(fields: list[dict[str, Any]], terms: tuple[str, ...]) -> list[dict[str, Any]]:
    return [field for field in fields if _matches(_field_blob(field), terms)]


def _matching_assets(assets: list[dict[str, Any]], terms: tuple[str, ...]) -> list[dict[str, Any]]:
    return [asset for asset in assets if _matches(_asset_blob(asset), terms)]


def _matching_graphs(
    executions: list[dict[str, Any]],
    patterns: dict[str, Any],
    terms: tuple[str, ...],
) -> list[dict[str, Any]]:
    hypothesis_by_id = {
        _text(hypothesis.get("hypothesis_id")): hypothesis
        for hypothesis in _record_list(patterns.get("hypotheses"))
    }
    matches: list[dict[str, Any]] = []
    for execution in executions:
        hypothesis = hypothesis_by_id.get(_text(execution.get("hypothesis_id")), {})
        if _matches(f"{_search_blob(execution)} {_search_blob(hypothesis)}", terms):
            matches.append(execution)
    return matches


def _why_built(
    title: str,
    fields: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    names = _names(fields, assets)
    if names != "connected evidence":
        parts.append(names)
    if graphs:
        parts.append(f"{len(graphs)} executed analyses")
    if not parts:
        parts.append("semantic roles in the connected data")
    return f"Because this data has {', '.join(parts)}, Baseflo built {title}."


def _execution_metrics(graphs: list[dict[str, Any]]) -> list[BusinessViewMetric]:
    metrics: list[BusinessViewMetric] = []
    for graph in graphs[:3]:
        result = _record(graph.get("result"))
        graph_id = _text(graph.get("graph_id"))
        if not result:
            continue
        metrics.append(
            BusinessViewMetric(
                label=_humanize(graph_id),
                value=str(result.get("row_count", 0)),
                unit="rows",
                why="Rows materialized by this analysis and available for drill-down.",
                evidence_refs=[graph_id] if graph_id else [],
            )
        )
    return metrics


def _drilldowns(
    spec: _SectionSpec,
    graph_refs: list[str],
    field_refs: list[str],
) -> list[BusinessViewDrilldown]:
    return [
        BusinessViewDrilldown(
            drilldown_id=f"{spec.kind}:{index + 1}",
            label=question,
            question=question,
            graph_refs=graph_refs,
            field_refs=field_refs,
            artifact_refs=[f"table:{graph_id}" for graph_id in graph_refs],
        )
        for index, question in enumerate(spec.questions[:3])
    ]


def _chart_refs(graphs: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for graph in graphs:
        chart_artifact_id = _text(_record(graph.get("source_refs")).get("chart_artifact_id"))
        graph_id = _text(graph.get("graph_id"))
        if chart_artifact_id:
            refs.append(f"chart:{chart_artifact_id}")
        elif graph_id:
            refs.append(f"chart:{graph_id}")
    return _unique(refs)


def _action_refs(graphs: list[dict[str, Any]]) -> list[str]:
    refs: list[str] = []
    for graph in graphs:
        for batch in _record_list(graph.get("action_batches")):
            for action in _record_list(batch.get("actions")):
                action_id = _text(action.get("action_id"))
                if action_id:
                    refs.append(f"action:{action_id}")
    return _unique(refs)


def _section_confidence(
    fields: list[dict[str, Any]],
    assets: list[dict[str, Any]],
    graphs: list[dict[str, Any]],
) -> float:
    raw = 0.45
    if assets:
        raw += 0.15
    if fields:
        raw += 0.2
    if graphs:
        raw += 0.15
    return min(raw, 0.95)


def _confidence(sections: list[BusinessViewSection]) -> float:
    if not sections:
        return 0.0
    return round(sum(section.confidence for section in sections) / len(sections), 2)


def _headline(business_model: dict[str, Any], sections: list[BusinessViewSection]) -> str:
    kind = _text(business_model.get("business_kind"), "business")
    if sections:
        return f"{kind.title()} operating view"
    return "Baseflo operating view"


def _names(fields: list[dict[str, Any]], assets: list[dict[str, Any]]) -> str:
    names = _unique(
        [
            *[
                _text(
                    field.get("measure_kind"),
                    _text(field.get("semantic_type"), _text(field.get("field_name"))),
                )
                for field in fields
            ],
            *[_text(asset.get("label"), _text(asset.get("role"))) for asset in assets],
        ]
    )
    return ", ".join(names[:5]) if names else "connected evidence"


def _field_blob(field: dict[str, Any]) -> str:
    return " ".join(
        _text(field.get(key))
        for key in ("field_id", "field_name", "semantic_type", "role", "measure_kind", "entity_hint")
    ).lower()


def _asset_blob(asset: dict[str, Any]) -> str:
    return " ".join(
        [
            *[_text(asset.get(key)) for key in ("asset_id", "role", "entity_type", "label", "why")],
            *[str(tag) for tag in _list(asset.get("tags"))],
        ]
    ).lower()


def _asset_tags(assets: list[dict[str, Any]]) -> list[str]:
    tags: list[str] = []
    for asset in assets:
        tags.extend(str(tag) for tag in _list(asset.get("tags")))
        tags.extend([_text(asset.get("role")), _text(asset.get("entity_type"))])
    return _unique(tags)


def _matches(blob: str, terms: tuple[str, ...]) -> bool:
    return any(term.lower() in blob for term in terms)


def _search_blob(value: Any) -> str:
    return str(value).lower()


def _humanize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title() if value else "Analysis"


def _dump(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value if isinstance(value, dict) else {}


def _record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def _record_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_record(item) for item in value if _record(item)]


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, fallback: str = "") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _unique(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _dedupe_sections(sections: list[BusinessViewSection]) -> list[BusinessViewSection]:
    by_id: dict[str, BusinessViewSection] = {}
    for section in sections:
        by_id[section.section_id] = section
    return sorted(by_id.values(), key=lambda section: _section_order(section.kind))


def _section_order(kind: str) -> int:
    order = {
        "sales": 10,
        "receivables": 20,
        "profit_loss": 30,
        "inventory": 40,
        "customers_parties": 50,
        "products_items": 60,
        "expenses": 70,
        "operations": 80,
        "data_quality": 90,
        "connected_data": 100,
    }
    return order.get(kind, 999)
