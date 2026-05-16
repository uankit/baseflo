from __future__ import annotations


def test_profile_values_detects_key_measure_time_and_quality() -> None:
    from app.data_profiler import has_candidate, profile_values

    customer_id = profile_values(
        field_id="field:customer_id",
        asset_id="asset:orders",
        name="customer_id",
        values=["1", "2", "3", "4"],
    )
    assert customer_id.observed_type == "integer"
    assert has_candidate(customer_id, "primary_key")
    assert has_candidate(customer_id, "identifier")

    amount = profile_values(
        field_id="field:pending",
        asset_id="asset:bills",
        name="pending_amount",
        values=["₹1,200", "2,400", "0", ""],
    )
    assert amount.observed_type == "money"
    assert has_candidate(amount, "measure")
    assert amount.blank_count == 1

    bill_date = profile_values(
        field_id="field:date",
        asset_id="asset:bills",
        name="bill_date",
        values=["2026-04-01", "2026-04-02"],
    )
    assert bill_date.observed_type == "date"
    assert has_candidate(bill_date, "timestamp")

    empty = profile_values(
        field_id="field:empty",
        asset_id="asset:bills",
        name="notes",
        values=[None, "", " "],
    )
    assert "all_null" in empty.quality_flags


def test_relationship_profile_uses_overlap_type_and_cardinality() -> None:
    from app.data_profiler import profile_values, relationship_profile

    customers_id = profile_values(
        field_id="customers.id",
        asset_id="customers",
        name="id",
        values=["c1", "c2", "c3", "c4"],
    )
    orders_customer_id = profile_values(
        field_id="orders.customer_id",
        asset_id="orders",
        name="customer_id",
        values=["c1", "c1", "c2", "c3", "c3"],
    )

    rel = relationship_profile(
        left=customers_id,
        right=orders_customer_id,
        shared_values=["c1", "c2", "c3"],
    )

    assert rel is not None
    assert rel.cardinality == "one_to_many"
    assert rel.overlap_ratio == 1.0
    assert rel.confidence >= 0.8
    assert rel.left_field_id == "customers.id"
    assert rel.right_field_id == "orders.customer_id"


def test_non_join_like_measure_fields_do_not_form_relationships() -> None:
    from app.data_profiler import profile_values, relationship_profile

    left = profile_values(
        field_id="orders.total",
        asset_id="orders",
        name="total_amount",
        values=["100", "200", "300"],
    )
    right = profile_values(
        field_id="expenses.total",
        asset_id="expenses",
        name="total_amount",
        values=["100", "200", "300"],
    )

    assert relationship_profile(left=left, right=right, shared_values=["100", "200", "300"]) is None
