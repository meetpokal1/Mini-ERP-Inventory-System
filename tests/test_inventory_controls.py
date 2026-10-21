import pandas as pd
import pytest

import database
from inventory_controls import build_cycle_count_review, build_replenishment_plan


def sample_products():
    return [
        {
            "product_id": 1,
            "sku": "SKU-A",
            "name": "Cable",
            "quantity_in_stock": 8,
            "reorder_level": 15,
            "unit_price": 100.0,
        },
        {
            "product_id": 2,
            "sku": "SKU-B",
            "name": "Cloth",
            "quantity_in_stock": 5,
            "reorder_level": 10,
            "unit_price": 20.0,
        },
    ]


def test_replenishment_plan_counts_pending_purchase_orders():
    plan = build_replenishment_plan(
        sample_products(),
        [
            {"product_id": 1, "quantity_ordered": 25, "status": "Pending"},
            {"product_id": 2, "quantity_ordered": 3, "status": "Received"},
        ],
    )
    cable = plan.loc[plan["sku"] == "SKU-A"].iloc[0]
    cloth = plan.loc[plan["sku"] == "SKU-B"].iloc[0]

    assert cable["projected_qty_after_pending_pos"] == 33
    assert cable["additional_qty_to_reach_threshold"] == 0
    assert cable["planning_status"] == "Covered by pending PO"
    assert cloth["pending_incoming_qty"] == 0
    assert cloth["additional_qty_to_reach_threshold"] == 5
    assert cloth["planning_status"] == "Review replenishment"


def test_cycle_count_review_calculates_variance_and_keeps_unknown_skus():
    counts = pd.DataFrame(
        {"sku": ["SKU-A", "SKU-B", "SKU-UNKNOWN"], "counted_qty": [6, 5, 4]}
    )
    review = build_cycle_count_review(sample_products(), counts).set_index("sku")

    assert review.loc["SKU-A", "variance_qty"] == -2
    assert review.loc["SKU-A", "variance_value_at_unit_price"] == -200.0
    assert review.loc["SKU-A", "status"] == "VARIANCE"
    assert review.loc["SKU-B", "status"] == "MATCH"
    assert review.loc["SKU-UNKNOWN", "status"] == "UNKNOWN_SKU"
    assert pd.isna(review.loc["SKU-UNKNOWN", "variance_qty"])


@pytest.mark.parametrize(
    "counts, message",
    [
        (pd.DataFrame({"sku": ["SKU-A", "sku-a"], "counted_qty": [1, 2]}), "Duplicate SKU"),
        (pd.DataFrame({"sku": ["SKU-A"], "counted_qty": [-1]}), "cannot be negative"),
        (pd.DataFrame({"sku": ["SKU-A"], "counted_qty": [1.5]}), "whole numbers"),
        (pd.DataFrame({"sku": ["SKU-A"], "counted_qty": ["many"]}), "Invalid counted quantity"),
    ],
)
def test_cycle_count_rejects_ambiguous_or_invalid_input(counts, message):
    with pytest.raises(ValueError, match=message):
        build_cycle_count_review(sample_products(), counts)


def setup_test_db(monkeypatch, tmp_path):
    db_file = tmp_path / "inventory-test.db"
    monkeypatch.setattr(database, "DB_PATH", str(db_file))
    database.init_db()
    database.add_supplier("Test Supplier")
    supplier_id = database.get_suppliers()[0]["supplier_id"]
    database.add_product("SKU-X", "Test Item", "Tests", 50.0, 5, 3, supplier_id)
    product_id = database.get_products()[0]["product_id"]
    return product_id, supplier_id


def test_stock_out_cannot_make_inventory_negative(monkeypatch, tmp_path):
    product_id, _ = setup_test_db(monkeypatch, tmp_path)

    with pytest.raises(ValueError, match="exceeds available stock"):
        database.adjust_stock(product_id, 6, "OUT", "test")
    assert database.get_products()[0]["quantity_in_stock"] == 5
    assert database.get_stock_movements() == []


def test_purchase_order_can_only_be_received_once(monkeypatch, tmp_path):
    product_id, supplier_id = setup_test_db(monkeypatch, tmp_path)
    database.create_purchase_order(product_id, supplier_id, 3)
    po_id = database.get_purchase_orders()[0]["po_id"]

    database.mark_po_received(po_id)
    assert database.get_products()[0]["quantity_in_stock"] == 8

    with pytest.raises(ValueError, match="already received"):
        database.mark_po_received(po_id)

    assert database.get_products()[0]["quantity_in_stock"] == 8
    assert len(database.get_stock_movements()) == 1


def test_cycle_count_adjustment_updates_stock_and_creates_audit_event(monkeypatch, tmp_path):
    product_id, _ = setup_test_db(monkeypatch, tmp_path)

    delta = database.set_stock_to_counted_quantity(
        product_id, 7, note="Verified physical count"
    )

    assert delta == 2
    assert database.get_products()[0]["quantity_in_stock"] == 7
    movement = database.get_stock_movements()[0]
    assert movement["movement_type"] == "IN"
    assert movement["change_qty"] == 2
    assert "Verified physical count" in movement["note"]
