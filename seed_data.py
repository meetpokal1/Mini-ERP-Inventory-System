"""
seed_data.py
Populates the database with realistic sample data so the app isn't empty
on first run. Safe to re-run - it wipes and recreates the DB each time.
"""

import os
from database import DB_PATH, init_db, add_supplier, add_product, get_suppliers, get_products, create_purchase_order

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

init_db()

# Suppliers
add_supplier("Kunal Enterprises", "Kunal Shah", "9820011122", "kunal@kunalent.com")
add_supplier("Patel Hardware Supplies", "Rakesh Patel", "9833344455", "sales@patelhardware.in")
add_supplier("Global Gems Ltd", "Anita Mehta", "9845566778", "procurement@globalgems.com")

suppliers = get_suppliers()
supplier_map = {s["name"]: s["supplier_id"] for s in suppliers}

# Products
add_product("SKU-001", "A4 Copier Paper (Ream)", "Office Supplies", 280.00, 45, 20, supplier_map["Patel Hardware Supplies"])
add_product("SKU-002", "USB-C Cable 1m", "Electronics", 199.00, 8, 15, supplier_map["Kunal Enterprises"])
add_product("SKU-003", "Wireless Mouse", "Electronics", 550.00, 30, 10, supplier_map["Kunal Enterprises"])
add_product("SKU-004", "Diamond Polishing Cloth", "Trade Supplies", 120.00, 5, 10, supplier_map["Global Gems Ltd"])
add_product("SKU-005", "Invoice Book (100 pages)", "Office Supplies", 65.00, 60, 25, supplier_map["Patel Hardware Supplies"])
add_product("SKU-006", "External HDD 1TB", "Electronics", 3200.00, 3, 5, supplier_map["Kunal Enterprises"])

products = get_products()
product_map = {p["sku"]: p["product_id"] for p in products}

# A couple of open purchase orders for low-stock items
create_purchase_order(product_map["SKU-002"], supplier_map["Kunal Enterprises"], 25)
create_purchase_order(product_map["SKU-006"], supplier_map["Kunal Enterprises"], 10)

print("Database seeded successfully with 3 suppliers, 6 products, and 2 open purchase orders.")
