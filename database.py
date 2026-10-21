"""
database.py
SQLite data layer for the Mini Inventory / ERP Management System.

Handles: suppliers, products/stock, purchase orders, and low-stock alerts.
Kept dependency-free (uses Python's built-in sqlite3) so it runs anywhere.
"""

import sqlite3
from datetime import datetime

DB_PATH = "inventory.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS suppliers (
            supplier_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_person TEXT,
            phone TEXT,
            email TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT,
            unit_price REAL NOT NULL,
            quantity_in_stock INTEGER NOT NULL DEFAULT 0,
            reorder_level INTEGER NOT NULL DEFAULT 10,
            supplier_id INTEGER,
            FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS purchase_orders (
            po_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            supplier_id INTEGER,
            quantity_ordered INTEGER NOT NULL,
            order_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            FOREIGN KEY (product_id) REFERENCES products (product_id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (supplier_id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            movement_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            change_qty INTEGER NOT NULL,
            movement_type TEXT NOT NULL,
            note TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (product_id) REFERENCES products (product_id)
        )
    """)

    conn.commit()
    conn.close()


# ---------- Suppliers ----------

def add_supplier(name, contact_person="", phone="", email=""):
    conn = get_connection()
    conn.execute(
        "INSERT INTO suppliers (name, contact_person, phone, email) VALUES (?, ?, ?, ?)",
        (name, contact_person, phone, email),
    )
    conn.commit()
    conn.close()


def get_suppliers():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM suppliers ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Products ----------

def add_product(sku, name, category, unit_price, quantity_in_stock, reorder_level, supplier_id=None):
    conn = get_connection()
    conn.execute(
        """INSERT INTO products (sku, name, category, unit_price, quantity_in_stock, reorder_level, supplier_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sku, name, category, unit_price, quantity_in_stock, reorder_level, supplier_id),
    )
    conn.commit()
    conn.close()


def get_products():
    conn = get_connection()
    rows = conn.execute("""
        SELECT p.*, s.name as supplier_name
        FROM products p
        LEFT JOIN suppliers s ON p.supplier_id = s.supplier_id
        ORDER BY p.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_low_stock_products():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM products WHERE quantity_in_stock <= reorder_level ORDER BY quantity_in_stock ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def adjust_stock(product_id, change_qty, movement_type, note=""):
    """Record one validated stock movement without allowing negative on-hand stock."""
    movement_type = str(movement_type).strip().upper()
    if movement_type not in {"IN", "OUT"}:
        raise ValueError("Movement type must be 'IN' or 'OUT'.")
    try:
        quantity = int(change_qty)
    except (TypeError, ValueError) as exc:
        raise ValueError("Movement quantity must be a positive whole number.") from exc
    if quantity <= 0 or str(change_qty).strip() != str(quantity):
        raise ValueError("Movement quantity must be a positive whole number.")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        product = cur.execute(
            "SELECT quantity_in_stock FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            raise ValueError("Product not found.")
        current_qty = int(product["quantity_in_stock"])
        if movement_type == "OUT" and quantity > current_qty:
            raise ValueError(
                f"Stock-out quantity ({quantity}) exceeds available stock ({current_qty})."
            )

        signed_qty = quantity if movement_type == "IN" else -quantity
        cur.execute(
            "UPDATE products SET quantity_in_stock = quantity_in_stock + ? WHERE product_id = ?",
            (signed_qty, product_id),
        )
        cur.execute(
            """INSERT INTO stock_movements (product_id, change_qty, movement_type, note, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (product_id, quantity, movement_type, note, datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
def get_stock_movements(product_id=None):
    conn = get_connection()
    if product_id:
        rows = conn.execute(
            "SELECT * FROM stock_movements WHERE product_id = ? ORDER BY timestamp DESC", (product_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM stock_movements ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Purchase Orders ----------

def create_purchase_order(product_id, supplier_id, quantity_ordered):
    conn = get_connection()
    conn.execute(
        """INSERT INTO purchase_orders (product_id, supplier_id, quantity_ordered, order_date, status)
           VALUES (?, ?, ?, ?, 'Pending')""",
        (product_id, supplier_id, quantity_ordered, datetime.now().strftime("%Y-%m-%d")),
    )
    conn.commit()
    conn.close()


def get_purchase_orders():
    conn = get_connection()
    rows = conn.execute("""
        SELECT po.*, p.name as product_name, s.name as supplier_name
        FROM purchase_orders po
        JOIN products p ON po.product_id = p.product_id
        LEFT JOIN suppliers s ON po.supplier_id = s.supplier_id
        ORDER BY po.order_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_stock_to_counted_quantity(product_id, counted_qty, note="Physical stock count reconciliation"):
    """Set on-hand stock to a verified physical count and record the variance atomically.

    Returns the signed stock change (counted quantity minus prior system quantity).
    """
    try:
        target_qty = int(counted_qty)
    except (TypeError, ValueError) as exc:
        raise ValueError("Counted quantity must be a non-negative whole number.") from exc
    if target_qty < 0 or str(counted_qty).strip() != str(target_qty):
        raise ValueError("Counted quantity must be a non-negative whole number.")

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        product = cur.execute(
            "SELECT quantity_in_stock FROM products WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        if product is None:
            raise ValueError("Product not found.")

        current_qty = int(product["quantity_in_stock"])
        delta = target_qty - current_qty
        if delta:
            movement_type = "IN" if delta > 0 else "OUT"
            audit_note = (
                f"{note}; system_qty={current_qty}; counted_qty={target_qty}; "
                f"variance={delta:+d}"
            )
            cur.execute(
                "UPDATE products SET quantity_in_stock = ? WHERE product_id = ?",
                (target_qty, product_id),
            )
            cur.execute(
                """INSERT INTO stock_movements (product_id, change_qty, movement_type, note, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (product_id, abs(delta), movement_type, audit_note, datetime.now().isoformat(timespec="seconds")),
            )
        conn.commit()
        return delta
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def mark_po_received(po_id):
    """Receive a pending PO exactly once, atomically updating stock and the audit log."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.cursor()
        po = cur.execute(
            "SELECT * FROM purchase_orders WHERE po_id = ?",
            (po_id,),
        ).fetchone()
        if po is None:
            raise ValueError("Purchase order not found.")
        if str(po["status"]).strip().casefold() != "pending":
            raise ValueError(f"Purchase order #{po_id} is already received or not pending.")

        updated = cur.execute(
            "UPDATE purchase_orders SET status = 'Received' WHERE po_id = ? AND status = 'Pending'",
            (po_id,),
        )
        if updated.rowcount != 1:
            raise ValueError(f"Purchase order #{po_id} is already received or not pending.")

        cur.execute(
            "UPDATE products SET quantity_in_stock = quantity_in_stock + ? WHERE product_id = ?",
            (int(po["quantity_ordered"]), int(po["product_id"])),
        )
        cur.execute(
            """INSERT INTO stock_movements (product_id, change_qty, movement_type, note, timestamp)
               VALUES (?, ?, 'IN', ?, ?)""",
            (
                int(po["product_id"]),
                int(po["quantity_ordered"]),
                f"Received against PO #{po_id}",
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
