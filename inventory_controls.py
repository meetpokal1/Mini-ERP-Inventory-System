"""Pure business rules for cycle-count reviews and replenishment planning."""

from __future__ import annotations

from collections import defaultdict
import math

import pandas as pd


def build_replenishment_plan(products, purchase_orders) -> pd.DataFrame:
    """Net pending purchase orders against on-hand stock before suggesting a reorder.

    The suggested quantity only closes the gap to the configured reorder threshold.
    It is a planning aid, not a demand forecast or purchase recommendation.
    """
    incoming_by_product = defaultdict(int)
    for order in purchase_orders:
        if str(order.get("status", "")).strip().casefold() == "pending":
            incoming_by_product[int(order["product_id"])] += int(order["quantity_ordered"])

    rows = []
    for product in products:
        on_hand = int(product["quantity_in_stock"])
        threshold = int(product["reorder_level"])
        incoming = incoming_by_product.get(int(product["product_id"]), 0)
        projected = on_hand + incoming
        shortfall = max(0, threshold - projected)

        if shortfall > 0:
            status = "Review replenishment"
        elif on_hand <= threshold and incoming > 0:
            status = "Covered by pending PO"
        else:
            status = "No action from threshold rule"

        rows.append(
            {
                "sku": product["sku"],
                "product_name": product["name"],
                "on_hand_qty": on_hand,
                "reorder_threshold": threshold,
                "pending_incoming_qty": incoming,
                "projected_qty_after_pending_pos": projected,
                "additional_qty_to_reach_threshold": shortfall,
                "planning_status": status,
            }
        )

    columns = [
        "sku",
        "product_name",
        "on_hand_qty",
        "reorder_threshold",
        "pending_incoming_qty",
        "projected_qty_after_pending_pos",
        "additional_qty_to_reach_threshold",
        "planning_status",
    ]
    return pd.DataFrame(rows, columns=columns).sort_values(
        ["additional_qty_to_reach_threshold", "sku"],
        ascending=[False, True],
        ignore_index=True,
    )


def build_cycle_count_review(products, count_df: pd.DataFrame) -> pd.DataFrame:
    """Compare an uploaded physical count (sku, counted_qty) with system stock.

    Unknown SKUs are retained as review exceptions but are never eligible for
    automatic stock adjustment. Duplicate SKU rows and invalid quantities are
    rejected so a batch cannot quietly double-count a product.
    """
    if not isinstance(count_df, pd.DataFrame):
        raise ValueError("Physical count input must be a CSV or Excel table.")
    if count_df.empty:
        raise ValueError("The physical count file contains no rows.")

    clean = count_df.copy()
    clean.columns = [str(column).strip().lower() for column in clean.columns]
    if len(set(clean.columns)) != len(clean.columns):
        raise ValueError("Column names must be unique after trimming spaces and case.")

    missing = [column for column in ("sku", "counted_qty") if column not in clean.columns]
    if missing:
        raise ValueError("Missing required column(s): " + ", ".join(missing))

    clean["sku"] = clean["sku"].fillna("").astype(str).str.strip()
    blank_sku = clean["sku"].eq("")
    if blank_sku.any():
        rows = [str(index + 2) for index in clean.index[blank_sku].tolist()]
        raise ValueError("Blank SKU on spreadsheet row(s): " + ", ".join(rows))

    normalised_skus = clean["sku"].str.casefold()
    duplicates = normalised_skus.duplicated(keep=False)
    if duplicates.any():
        values = sorted(clean.loc[duplicates, "sku"].unique().tolist())
        raise ValueError("Duplicate SKU(s) in physical count file: " + ", ".join(values))

    numeric_qty = pd.to_numeric(clean["counted_qty"], errors="coerce")
    invalid = numeric_qty.isna() | ~numeric_qty.map(
        lambda value: math.isfinite(float(value)) if pd.notna(value) else False
    )
    if invalid.any():
        rows = [str(index + 2) for index in clean.index[invalid].tolist()]
        raise ValueError("Invalid counted quantity on spreadsheet row(s): " + ", ".join(rows))

    non_integer = numeric_qty.map(lambda value: float(value) % 1 != 0)
    if non_integer.any():
        rows = [str(index + 2) for index in clean.index[non_integer].tolist()]
        raise ValueError("Counted quantities must be whole numbers; check row(s): " + ", ".join(rows))

    negative = numeric_qty < 0
    if negative.any():
        rows = [str(index + 2) for index in clean.index[negative].tolist()]
        raise ValueError("Counted quantities cannot be negative; check row(s): " + ", ".join(rows))

    product_by_sku = {
        str(product["sku"]).strip().casefold(): product
        for product in products
    }

    rows = []
    for _, record in clean.iterrows():
        sku = record["sku"]
        counted = int(record["counted_qty"])
        product = product_by_sku.get(sku.casefold())

        if product is None:
            rows.append(
                {
                    "sku": sku,
                    "product_name": "Unknown SKU",
                    "system_qty": None,
                    "counted_qty": counted,
                    "variance_qty": None,
                    "unit_price": None,
                    "variance_value_at_unit_price": None,
                    "status": "UNKNOWN_SKU",
                    "suggested_review": "Check the SKU spelling or create the product record before posting any adjustment.",
                }
            )
            continue

        system_qty = int(product["quantity_in_stock"])
        variance = counted - system_qty
        price = float(product["unit_price"])
        rows.append(
            {
                "sku": sku,
                "product_name": product["name"],
                "system_qty": system_qty,
                "counted_qty": counted,
                "variance_qty": variance,
                "unit_price": price,
                "variance_value_at_unit_price": round(variance * price, 2),
                "status": "MATCH" if variance == 0 else "VARIANCE",
                "suggested_review": (
                    "No adjustment required."
                    if variance == 0
                    else "Check unrecorded receipts, sales, returns, damage, or unit-of-measure errors; confirm the count before posting."
                ),
            }
        )

    return pd.DataFrame(
        rows,
        columns=[
            "sku",
            "product_name",
            "system_qty",
            "counted_qty",
            "variance_qty",
            "unit_price",
            "variance_value_at_unit_price",
            "status",
            "suggested_review",
        ],
    )
