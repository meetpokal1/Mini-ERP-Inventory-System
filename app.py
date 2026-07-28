"""
app.py
Streamlit dashboard for the Mini Inventory / ERP Management System.

Run with:
    streamlit run app.py
"""

import os
import streamlit as st
import pandas as pd
from database import (
    DB_PATH, init_db, add_supplier, add_product, get_suppliers, get_products,
    get_low_stock_products, adjust_stock, create_purchase_order,
    get_purchase_orders, mark_po_received,
)

if not os.path.exists(DB_PATH):
    init_db()

st.set_page_config(page_title="Mini Inventory / ERP System", layout="wide")
st.title("📦 Mini Inventory / ERP Management System")

tab_dashboard, tab_products, tab_stock, tab_po, tab_suppliers = st.tabs(
    ["Dashboard", "Products", "Stock Movement", "Purchase Orders", "Suppliers"]
)

# ---------------- DASHBOARD ----------------
with tab_dashboard:
    products = get_products()
    low_stock = get_low_stock_products()
    pos = get_purchase_orders()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Products (SKUs)", len(products))
    total_value = sum(p["unit_price"] * p["quantity_in_stock"] for p in products)
    col2.metric("Total Stock Value", f"₹{total_value:,.0f}")
    col3.metric("Low Stock Alerts", len(low_stock))
    pending_pos = len([po for po in pos if po["status"] == "Pending"])
    col4.metric("Pending Purchase Orders", pending_pos)

    if low_stock:
        st.subheader("⚠️ Low Stock Alerts")
        st.dataframe(pd.DataFrame(low_stock)[["sku", "name", "quantity_in_stock", "reorder_level"]],
                     use_container_width=True, hide_index=True)
    else:
        st.success("No products are below their reorder level.")

# ---------------- PRODUCTS ----------------
with tab_products:
    st.subheader("All Products")
    products = get_products()
    if products:
        df = pd.DataFrame(products)[["sku", "name", "category", "unit_price", "quantity_in_stock", "reorder_level", "supplier_name"]]
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No products yet - add one below.")

    st.subheader("Add New Product")
    suppliers = get_suppliers()
    supplier_options = {s["name"]: s["supplier_id"] for s in suppliers}

    with st.form("add_product_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sku = c1.text_input("SKU")
        name = c2.text_input("Product Name")
        category = c1.text_input("Category")
        unit_price = c2.number_input("Unit Price (₹)", min_value=0.0, step=1.0)
        qty = c1.number_input("Opening Stock Qty", min_value=0, step=1)
        reorder = c2.number_input("Reorder Level", min_value=0, step=1, value=10)
        supplier_name = st.selectbox("Supplier", options=["(none)"] + list(supplier_options.keys()))
        submitted = st.form_submit_button("Add Product")

        if submitted:
            if not sku or not name:
                st.error("SKU and Product Name are required.")
            else:
                supplier_id = supplier_options.get(supplier_name) if supplier_name != "(none)" else None
                try:
                    add_product(sku, name, category, unit_price, int(qty), int(reorder), supplier_id)
                    st.success(f"Added product {sku} - {name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not add product (maybe SKU already exists?): {e}")

# ---------------- STOCK MOVEMENT ----------------
with tab_stock:
    st.subheader("Record Stock In / Out")
    products = get_products()
    product_options = {f"{p['sku']} - {p['name']}": p["product_id"] for p in products}

    if product_options:
        with st.form("stock_movement_form", clear_on_submit=True):
            product_label = st.selectbox("Product", options=list(product_options.keys()))
            movement_type = st.radio("Movement Type", options=["IN", "OUT"], horizontal=True)
            qty = st.number_input("Quantity", min_value=1, step=1)
            note = st.text_input("Note (optional)", placeholder="e.g. Sold to walk-in customer")
            submitted = st.form_submit_button("Record Movement")

            if submitted:
                adjust_stock(product_options[product_label], int(qty), movement_type, note)
                st.success(f"Recorded {movement_type} of {qty} unit(s) for {product_label}")
                st.rerun()
    else:
        st.info("Add a product first before recording stock movements.")

# ---------------- PURCHASE ORDERS ----------------
with tab_po:
    st.subheader("Purchase Orders")
    pos = get_purchase_orders()
    if pos:
        st.dataframe(pd.DataFrame(pos)[["po_id", "product_name", "supplier_name", "quantity_ordered", "order_date", "status"]],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No purchase orders yet.")

    st.subheader("Create Purchase Order")
    products = get_products()
    suppliers = get_suppliers()
    product_options = {f"{p['sku']} - {p['name']}": p["product_id"] for p in products}
    supplier_options = {s["name"]: s["supplier_id"] for s in suppliers}

    if product_options and supplier_options:
        with st.form("create_po_form", clear_on_submit=True):
            product_label = st.selectbox("Product", options=list(product_options.keys()))
            supplier_name = st.selectbox("Supplier", options=list(supplier_options.keys()))
            qty = st.number_input("Quantity to Order", min_value=1, step=1)
            submitted = st.form_submit_button("Create PO")

            if submitted:
                create_purchase_order(product_options[product_label], supplier_options[supplier_name], int(qty))
                st.success("Purchase order created.")
                st.rerun()
    else:
        st.info("Add at least one product and one supplier first.")

    pending_pos = [po for po in pos if po["status"] == "Pending"]
    if pending_pos:
        st.subheader("Mark PO as Received")
        po_options = {f"PO #{po['po_id']} - {po['product_name']} ({po['quantity_ordered']} units)": po["po_id"] for po in pending_pos}
        selected_po_label = st.selectbox("Select PO", options=list(po_options.keys()))
        if st.button("Mark as Received (auto-adds stock)"):
            mark_po_received(po_options[selected_po_label])
            st.success("PO marked as received and stock updated.")
            st.rerun()

# ---------------- SUPPLIERS ----------------
with tab_suppliers:
    st.subheader("All Suppliers")
    suppliers = get_suppliers()
    if suppliers:
        st.dataframe(pd.DataFrame(suppliers), use_container_width=True, hide_index=True)
    else:
        st.info("No suppliers yet - add one below.")

    st.subheader("Add New Supplier")
    with st.form("add_supplier_form", clear_on_submit=True):
        name = st.text_input("Supplier Name")
        contact = st.text_input("Contact Person")
        phone = st.text_input("Phone")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Add Supplier")

        if submitted:
            if not name:
                st.error("Supplier name is required.")
            else:
                add_supplier(name, contact, phone, email)
                st.success(f"Added supplier: {name}")
                st.rerun()
