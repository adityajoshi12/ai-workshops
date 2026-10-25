"""SQLite + CSV database layer for the ReturnFlow e-commerce workshop.

On first import (or when `reset_database()` is run), this module creates the
SQLite tables in `data/store.db` and seeds `orders` and `inventory` from
`data/orders.csv` and `data/inventory.csv`.

All agent tool calls (order lookup, damage inspection logging, inventory
checks, exchanges, refunds, and guardrail escalations) read and write real
SQLite rows so workshop attendees can inspect live state changes with
`python3 db_cli.py status`.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import os
import sqlite3
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
ORDERS_CSV = DATA_DIR / "orders.csv"
INVENTORY_CSV = DATA_DIR / "inventory.csv"


def _resolve_default_db_path() -> Path:
    """Use `data/store.db` when writable, falling back to `/tmp/returnflow_store.db` in read-only containers."""
    env_path = os.environ.get("RETURNFLOW_DB_PATH")
    if env_path:
        return Path(env_path)
    local_path = DATA_DIR / "store.db"
    if os.access(DATA_DIR, os.W_OK):
        return local_path
    return Path("/tmp/returnflow_store.db")


DEFAULT_DB_PATH = _resolve_default_db_path()

RETURN_WINDOW_DAYS = 30
EXCHANGE_BONUS_CREDIT_USD = 15.00
AUTO_REFUND_LIMITS_BY_TIER: dict[str, float] = {
    "Standard": 150.00,
    "Gold": 300.00,
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    customer_tier TEXT NOT NULL,
    sku TEXT NOT NULL,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    variant TEXT NOT NULL,
    price_usd REAL NOT NULL,
    days_since_delivery INTEGER NOT NULL,
    is_final_sale INTEGER NOT NULL DEFAULT 0,
    order_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
    sku TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    variant TEXT NOT NULL,
    price_usd REAL NOT NULL,
    stock_qty INTEGER NOT NULL,
    warehouse_location TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS return_inspections (
    inspection_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    condition_category TEXT NOT NULL,
    visual_findings TEXT NOT NULL,
    eligible_for_return INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS resolutions (
    resolution_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    resolution_type TEXT NOT NULL,
    new_sku TEXT,
    refund_amount_usd REAL NOT NULL DEFAULT 0.0,
    bonus_store_credit_usd REAL NOT NULL DEFAULT 0.0,
    return_label_code TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS escalations (
    ticket_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_tier TEXT NOT NULL,
    requested_amount_usd REAL NOT NULL,
    tier_limit_usd REAL NOT NULL,
    block_reason TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Return a SQLite connection with dict-like Row factory."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_initialized(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Create tables and seed from CSV files if the orders table is empty."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        if count == 0:
            _seed_from_csv(conn)


def reset_database(db_path: Path = DEFAULT_DB_PATH) -> dict[str, int]:
    """Drop all tables, recreate schema, and re-seed from CSV files."""
    with get_connection(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS inventory;
            DROP TABLE IF EXISTS return_inspections;
            DROP TABLE IF EXISTS resolutions;
            DROP TABLE IF EXISTS escalations;
            """
        )
        conn.executescript(SCHEMA_SQL)
        return _seed_from_csv(conn)


def _seed_from_csv(conn: sqlite3.Connection) -> dict[str, int]:
    orders_loaded = 0
    with ORDERS_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute(
                """
                INSERT INTO orders (
                    order_id, customer_name, customer_email, customer_tier,
                    sku, product_name, category, variant, price_usd,
                    days_since_delivery, is_final_sale, order_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["order_id"].strip(),
                    row["customer_name"].strip(),
                    row["customer_email"].strip(),
                    row["customer_tier"].strip(),
                    row["sku"].strip(),
                    row["product_name"].strip(),
                    row["category"].strip(),
                    row["variant"].strip(),
                    float(row["price_usd"]),
                    int(row["days_since_delivery"]),
                    1 if row["is_final_sale"].strip().lower() == "true" else 0,
                    row["order_status"].strip(),
                ),
            )
            orders_loaded += 1

    inventory_loaded = 0
    with INVENTORY_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conn.execute(
                """
                INSERT INTO inventory (
                    sku, product_name, category, variant,
                    price_usd, stock_qty, warehouse_location
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["sku"].strip(),
                    row["product_name"].strip(),
                    row["category"].strip(),
                    row["variant"].strip(),
                    float(row["price_usd"]),
                    int(row["stock_qty"]),
                    row["warehouse_location"].strip(),
                ),
            )
            inventory_loaded += 1

    conn.commit()
    return {"orders": orders_loaded, "inventory": inventory_loaded}


def fetch_order(order_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    """Fetch a single order by ID (case-insensitive)."""
    ensure_initialized(db_path)
    normalized_id = order_id.strip().upper()
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE UPPER(order_id) = ?",
            (normalized_id,),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["is_final_sale"] = bool(data["is_final_sale"])
        tier = data["customer_tier"]
        data["auto_refund_limit_usd"] = AUTO_REFUND_LIMITS_BY_TIER.get(tier, 150.0)
        data["within_return_window"] = data["days_since_delivery"] <= RETURN_WINDOW_DAYS
        return data


def search_inventory_by_product(
    product_name: str, db_path: Path = DEFAULT_DB_PATH
) -> list[dict[str, Any]]:
    """Return all SKU variants matching a product name substring."""
    ensure_initialized(db_path)
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM inventory
            WHERE LOWER(product_name) LIKE ?
            ORDER BY sku ASC
            """,
            (f"%{product_name.strip().lower()}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def log_inspection(
    order_id: str,
    condition_category: str,
    visual_findings: str,
    eligible_for_return: bool,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Insert a visual damage/condition inspection record into SQLite."""
    ensure_initialized(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with get_connection(db_path) as conn:
        seq = conn.execute("SELECT COUNT(*) FROM return_inspections").fetchone()[0] + 1
        inspection_id = f"INSP-{100 + seq}"
        conn.execute(
            """
            INSERT INTO return_inspections (
                inspection_id, order_id, condition_category,
                visual_findings, eligible_for_return, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                inspection_id,
                order_id.strip().upper(),
                condition_category,
                visual_findings,
                1 if eligible_for_return else 0,
                now,
            ),
        )
        conn.commit()
    return {
        "inspection_id": inspection_id,
        "order_id": order_id.strip().upper(),
        "condition_category": condition_category,
        "visual_findings": visual_findings,
        "eligible_for_return": eligible_for_return,
        "created_at": now,
    }


def create_exchange_resolution(
    order_id: str,
    target_sku: str,
    notes: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Decrement warehouse stock for `target_sku` and record an exchange with bonus store credit."""
    ensure_initialized(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    normalized_order = order_id.strip().upper()
    normalized_sku = target_sku.strip().upper()

    with get_connection(db_path) as conn:
        sku_row = conn.execute(
            "SELECT * FROM inventory WHERE UPPER(sku) = ?",
            (normalized_sku,),
        ).fetchone()
        if not sku_row:
            return {
                "status": "error",
                "error_message": f"SKU '{normalized_sku}' not found in warehouse inventory.",
            }
        if sku_row["stock_qty"] <= 0:
            return {
                "status": "error",
                "error_message": (
                    f"SKU '{normalized_sku}' ({sku_row['product_name']} - {sku_row['variant']}) "
                    "is currently out of stock (0 available)."
                ),
            }

        seq = conn.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] + 1
        resolution_id = f"EXCH-{200 + seq}"
        return_label = f"RMA-QR-{normalized_order}-{200 + seq}"

        conn.execute(
            "UPDATE inventory SET stock_qty = stock_qty - 1 WHERE UPPER(sku) = ?",
            (normalized_sku,),
        )
        conn.execute(
            "UPDATE orders SET order_status = 'EXCHANGE_ISSUED' WHERE UPPER(order_id) = ?",
            (normalized_order,),
        )
        conn.execute(
            """
            INSERT INTO resolutions (
                resolution_id, order_id, resolution_type, new_sku,
                refund_amount_usd, bonus_store_credit_usd,
                return_label_code, notes, created_at
            ) VALUES (?, ?, 'EXCHANGE', ?, 0.0, ?, ?, ?, ?)
            """,
            (
                resolution_id,
                normalized_order,
                normalized_sku,
                EXCHANGE_BONUS_CREDIT_USD,
                return_label,
                notes,
                now,
            ),
        )
        conn.commit()

        return {
            "status": "success",
            "resolution_id": resolution_id,
            "resolution_type": "EXCHANGE",
            "order_id": normalized_order,
            "replacement_sku": normalized_sku,
            "replacement_variant": sku_row["variant"],
            "warehouse_shipped_from": sku_row["warehouse_location"],
            "remaining_stock_qty": sku_row["stock_qty"] - 1,
            "bonus_store_credit_usd": EXCHANGE_BONUS_CREDIT_USD,
            "prepaid_return_label": return_label,
            "created_at": now,
        }


def create_refund_resolution(
    order_id: str,
    refund_amount_usd: float,
    reason: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Record an approved refund and generate a prepaid return shipping label."""
    ensure_initialized(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    normalized_order = order_id.strip().upper()

    with get_connection(db_path) as conn:
        seq = conn.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] + 1
        resolution_id = f"RFND-{300 + seq}"
        return_label = f"RMA-QR-{normalized_order}-{300 + seq}"

        conn.execute(
            "UPDATE orders SET order_status = 'REFUNDED' WHERE UPPER(order_id) = ?",
            (normalized_order,),
        )
        conn.execute(
            """
            INSERT INTO resolutions (
                resolution_id, order_id, resolution_type, new_sku,
                refund_amount_usd, bonus_store_credit_usd,
                return_label_code, notes, created_at
            ) VALUES (?, ?, 'REFUND', NULL, ?, 0.0, ?, ?, ?)
            """,
            (
                resolution_id,
                normalized_order,
                round(float(refund_amount_usd), 2),
                return_label,
                reason,
                now,
            ),
        )
        conn.commit()

    return {
        "status": "success",
        "resolution_id": resolution_id,
        "resolution_type": "REFUND",
        "order_id": normalized_order,
        "refund_amount_usd": round(float(refund_amount_usd), 2),
        "prepaid_return_label": return_label,
        "reason": reason,
        "created_at": now,
    }


def create_escalation_ticket(
    order_id: str,
    customer_tier: str,
    requested_amount_usd: float,
    tier_limit_usd: float,
    block_reason: str,
    db_path: Path = DEFAULT_DB_PATH,
) -> dict[str, Any]:
    """Insert a human-supervisor escalation ticket when a guardrail blocks a tool call."""
    ensure_initialized(db_path)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    normalized_order = order_id.strip().upper()

    with get_connection(db_path) as conn:
        seq = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0] + 1
        ticket_id = f"ESC-{900 + seq}"
        conn.execute(
            """
            INSERT INTO escalations (
                ticket_id, order_id, customer_tier, requested_amount_usd,
                tier_limit_usd, block_reason, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING_SUPERVISOR_REVIEW', ?)
            """,
            (
                ticket_id,
                normalized_order,
                customer_tier,
                round(float(requested_amount_usd), 2),
                round(float(tier_limit_usd), 2),
                block_reason,
                now,
            ),
        )
        conn.execute(
            "UPDATE orders SET order_status = 'ESCALATED_TO_SUPERVISOR' WHERE UPPER(order_id) = ?",
            (normalized_order,),
        )
        conn.commit()

    return {
        "ticket_id": ticket_id,
        "order_id": normalized_order,
        "customer_tier": customer_tier,
        "requested_amount_usd": round(float(requested_amount_usd), 2),
        "tier_limit_usd": round(float(tier_limit_usd), 2),
        "block_reason": block_reason,
        "status": "PENDING_SUPERVISOR_REVIEW",
        "created_at": now,
    }
