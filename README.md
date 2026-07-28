# Mini Inventory / ERP Management System

A simplified, working ERP module for inventory management — built to
understand the core data flows (products, suppliers, purchase orders, stock
movement) that real ERP platforms are built around.

## Problem Statement

Small businesses often track inventory in spreadsheets, which don't scale:
no automatic low-stock alerts, no audit trail of stock changes, and manual
purchase-order follow-up. This project implements the core of what an
ERP inventory module actually does, end to end:

- Maintain a product catalog with SKU, price, stock level, and reorder threshold
- Track suppliers and link them to products
- Record every stock movement (IN/OUT) with a timestamped audit trail
- Auto-flag products that have fallen below their reorder level
- Create purchase orders, and automatically update stock when a PO is marked "Received"

## Tech Stack

- **Python 3** + built-in **sqlite3** — no external DB server needed
- **Streamlit** — interactive dashboard UI
- **pandas** — for displaying/formatting tables in the UI

## Project Structure

```
mini-erp-inventory/
├── app.py             # Streamlit dashboard (5 tabs: Dashboard, Products, Stock, POs, Suppliers)
├── database.py         # SQLite schema + all data access functions
├── seed_data.py         # Populates sample suppliers/products/POs for a demo
├── requirements.txt
└── README.md
```

## Data Model

- **suppliers** → id, name, contact info
- **products** → SKU, name, category, price, quantity_in_stock, reorder_level, linked supplier
- **purchase_orders** → product, supplier, quantity ordered, status (Pending/Received)
- **stock_movements** → full audit log of every stock IN/OUT with timestamp and note

## How to Run

```bash
pip install -r requirements.txt
python seed_data.py        # creates and populates inventory.db with sample data
streamlit run app.py
```

The dashboard opens with:
- **Dashboard** — key metrics + low-stock alerts at a glance
- **Products** — view/add products
- **Stock Movement** — record stock in/out (e.g. sale, damage, new stock received)
- **Purchase Orders** — raise a PO to a supplier, and mark it received (auto-updates stock)
- **Suppliers** — manage supplier records

## Sample Data

`seed_data.py` creates 3 suppliers, 6 products (including a few already below
their reorder level to demonstrate the low-stock alerts), and 2 open purchase
orders.

## What I'd Improve Next

- Add user authentication/roles (admin vs. staff)
- Add reporting: stock valuation over time, fast/slow-moving items
- Migrate from SQLite to PostgreSQL for a more production-realistic setup
- Deploy on Streamlit Community Cloud for a live demo link

## Why I Built This

This scoped-down inventory module represents the core logic behind ERP
systems — the area I'm aiming to specialize in. Building it from scratch
(schema design, business rules like auto-updating stock on PO receipt, and a
usable UI) gave me hands-on understanding of what ERP software actually
automates.
