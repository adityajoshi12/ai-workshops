#!/usr/bin/env python3
"""CLI utility to inspect, reset, or smoke-test the ReturnFlow SQLite database.

Usage:
    python3 db_cli.py status            # Print current orders, stock, inspections, resolutions & escalations
    python3 db_cli.py reset             # Re-seed store.db from returnflow_agent/data/*.csv
    python3 db_cli.py test-guardrails   # Run an offline check of the SQLite tools & policy guardrails
"""
from __future__ import annotations

import argparse
from typing import Any

from returnflow_agent import db


def _print_table(title: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    print(f"\n=== {title} ({len(rows)} rows) ===")
    if not rows:
        print("  (empty)")
        return
    widths = {
        col: max(len(col), *(len(str(r.get(col, ""))) for r in rows))
        for col in columns
    }
    header = " | ".join(col.ljust(widths[col]) for col in columns)
    print("  " + header)
    print("  " + "-+-".join("-" * widths[col] for col in columns))
    for r in rows:
        line = " | ".join(str(r.get(col, "")).ljust(widths[col]) for col in columns)
        print("  " + line)


def cmd_status() -> None:
    db.ensure_initialized()
    with db.get_connection() as conn:
        orders = [dict(r) for r in conn.execute("SELECT * FROM orders ORDER BY order_id").fetchall()]
        inventory = [dict(r) for r in conn.execute("SELECT * FROM inventory ORDER BY sku").fetchall()]
        inspections = [dict(r) for r in conn.execute("SELECT * FROM return_inspections ORDER BY inspection_id").fetchall()]
        resolutions = [dict(r) for r in conn.execute("SELECT * FROM resolutions ORDER BY resolution_id").fetchall()]
        escalations = [dict(r) for r in conn.execute("SELECT * FROM escalations ORDER BY ticket_id").fetchall()]

    _print_table(
        "ORDERS (returnflow_agent/data/store.db)",
        orders,
        [
            "order_id",
            "customer_name",
            "customer_tier",
            "sku",
            "product_name",
            "variant",
            "price_usd",
            "days_since_delivery",
            "order_status",
        ],
    )
    _print_table(
        "WAREHOUSE INVENTORY",
        inventory,
        ["sku", "product_name", "variant", "price_usd", "stock_qty", "warehouse_location"],
    )
    _print_table(
        "VISUAL INSPECTIONS",
        inspections,
        ["inspection_id", "order_id", "condition_category", "eligible_for_return", "visual_findings"],
    )
    _print_table(
        "RESOLUTIONS (EXCHANGES & REFUNDS)",
        resolutions,
        [
            "resolution_id",
            "order_id",
            "resolution_type",
            "new_sku",
            "refund_amount_usd",
            "bonus_store_credit_usd",
            "return_label_code",
        ],
    )
    _print_table(
        "SUPERVISOR ESCALATIONS (GUARDRAIL TRIGGERS)",
        escalations,
        [
            "ticket_id",
            "order_id",
            "customer_tier",
            "requested_amount_usd",
            "tier_limit_usd",
            "status",
            "block_reason",
        ],
    )
    print()


def cmd_reset() -> None:
    counts = db.reset_database()
    print(
        f"Reset complete: seeded {counts['orders']} orders and "
        f"{counts['inventory']} inventory SKUs into {db.DEFAULT_DB_PATH}."
    )


def cmd_test_guardrails() -> None:
    """Verify tools and `refund_policy_guardrail` across the 4 workshop scenarios."""
    from returnflow_agent.agent import (
        check_exchange_stock,
        issue_refund,
        lookup_order,
        process_exchange,
        record_damage_assessment,
        refund_policy_guardrail,
    )

    class _MockTool:
        def __init__(self, name: str) -> None:
            self.name = name

    class _MockToolContext:
        def __init__(self) -> None:
            self.state: dict[str, Any] = {}

    db.reset_database()
    print("Running ReturnFlow SQLite + Guardrail verification...\n")

    # Scenario 1: ORD-1001 Size Swap Exchange (+ $15 bonus credit)
    ctx1 = _MockToolContext()
    lookup_order("ORD-1001", ctx1)
    record_damage_assessment(
        "ORD-1001",
        "unworn_new",
        "Brand-new blue and orange trail running shoes in box with tag attached.",
        ctx1,
    )
    check_exchange_stock("TrailBlaze Waterproof Running Shoes", ctx1)
    guard1 = refund_policy_guardrail(
        _MockTool("process_exchange"),
        {"order_id": "ORD-1001", "target_sku": "SKU-SHOE-10", "notes": "Size 9 -> Size 10"},
        ctx1,
    )
    assert guard1 is None, f"Expected None, got {guard1}"
    res1 = process_exchange("ORD-1001", "SKU-SHOE-10", "Size 9 -> Size 10", ctx1)
    print(f"[PASS] Scenario 1 (ORD-1001 Exchange): {res1['resolution_id']} | Bonus=${res1['bonus_store_credit_usd']} | Label={res1['prepaid_return_label']}")

    # Scenario 2: ORD-1002 Cracked Smartwatch -> Out of stock -> Auto-Refund ($135 <= $150 cap)
    ctx2 = _MockToolContext()
    lookup_order("ORD-1002", ctx2)
    record_damage_assessment(
        "ORD-1002",
        "damaged_in_transit",
        "Shattered front glass screen on ChronoFit Smart Watch.",
        ctx2,
    )
    guard2 = refund_policy_guardrail(
        _MockTool("issue_refund"),
        {"order_id": "ORD-1002", "refund_amount_usd": 135.0, "reason": "Damaged in transit, 0 stock"},
        ctx2,
    )
    assert guard2 is None, f"Expected None, got {guard2}"
    res2 = issue_refund("ORD-1002", 135.0, "Damaged in transit, 0 stock", ctx2)
    print(f"[PASS] Scenario 2 (ORD-1002 Auto-Refund): {res2['resolution_id']} | Refund=${res2['refund_amount_usd']} | Label={res2['prepaid_return_label']}")

    # Scenario 3: ORD-1003 $450 Espresso Machine -> Guardrail Escalates ($450 > $150 Standard cap)
    ctx3 = _MockToolContext()
    lookup_order("ORD-1003", ctx3)
    record_damage_assessment(
        "ORD-1003",
        "unworn_new",
        "Unopened box, customer wants cash refund.",
        ctx3,
    )
    guard3 = refund_policy_guardrail(
        _MockTool("issue_refund"),
        {"order_id": "ORD-1003", "refund_amount_usd": 450.0, "reason": "Customer requested refund"},
        ctx3,
    )
    assert guard3 is not None and guard3["status"] == "escalated_to_supervisor"
    print(f"[PASS] Scenario 3 (ORD-1003 High-Value Guardrail): Escalated -> {guard3['escalation_ticket']['ticket_id']}")

    # Scenario 4: ORD-1004 Heavily Used Muddy Boots (and 45 days post-delivery) -> Guardrail Blocks
    ctx4 = _MockToolContext()
    lookup_order("ORD-1004", ctx4)
    record_damage_assessment(
        "ORD-1004",
        "heavily_used",
        "Boots are heavily creased, scuffed, and covered in dried mud.",
        ctx4,
    )
    guard4 = refund_policy_guardrail(
        _MockTool("issue_refund"),
        {"order_id": "ORD-1004", "refund_amount_usd": 180.0, "reason": "Customer wants refund"},
        ctx4,
    )
    assert guard4 is not None and guard4["status"] == "blocked_by_guardrail"
    print(f"[PASS] Scenario 4 (ORD-1004 Policy Block): Blocked -> {guard4['policy_rule']}")

    # Reset DB back to clean initial state after self-test
    db.reset_database()
    print("\nAll 4 scenarios verified! Database reset to clean initial seed state.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ReturnFlow SQLite DB helper")
    parser.add_argument(
        "command",
        choices=["status", "reset", "test-guardrails"],
        help="Command to execute",
    )
    args = parser.parse_args()
    if args.command == "status":
        cmd_status()
    elif args.command == "reset":
        cmd_reset()
    elif args.command == "test-guardrails":
        cmd_test_guardrails()


if __name__ == "__main__":
    main()
