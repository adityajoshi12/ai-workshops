"""ReturnFlow: Autonomous E-Commerce Returns, Exchanges & Visual Damage Triage.

Multi-agent Google ADK system backed by SQLite + CSV seed data:
  1. `order_lookup_agent`  - Verifies order ID in SQLite and stores order context
                             in `ToolContext.state["active_order"]`.
  2. `visual_triage_agent` - Uses Gemini Multimodal Vision to inspect customer-
                             uploaded return photos in `adk web` and records a
                             structured inspection in SQLite + session state.
  3. `resolution_agent`    - Retention-first specialist that checks warehouse
                             inventory for instant exchanges (+ $15 bonus credit)
                             or issues refunds, protected by a deterministic
                             `before_tool_callback` (`refund_policy_guardrail`).
  4. `root_agent`          - Coordinator (`returns_concierge`) that routes the
                             conversation across the three specialists.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from google.adk.agents import Agent
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from . import db

MODEL = os.environ.get("RETURNFLOW_MODEL", "gemini-2.5-flash")

# Ensure the SQLite database is created and seeded from CSVs on startup
db.ensure_initialized()


# ---------------------------------------------------------------------------
# 1. Tools for `order_lookup_agent`
# ---------------------------------------------------------------------------
def lookup_order(order_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Look up an e-commerce order by order ID in the store SQLite database.

    Args:
        order_id: The order identifier such as 'ORD-1001' or 'ORD-1002'.

    Returns:
        A dict with 'status' ('success' or 'error') and the order record,
        return window status, and customer tier auto-refund limit.
    """
    order = db.fetch_order(order_id)
    if not order:
        return {
            "status": "error",
            "error_message": (
                f"Order '{order_id}' was not found. Valid sample order IDs are "
                "ORD-1001, ORD-1002, ORD-1003, ORD-1004, and ORD-1005."
            ),
        }

    # Save verified order into shared ADK session state so downstream agents
    # and guardrail callbacks can read it deterministically.
    tool_context.state["active_order"] = order
    tool_context.state["customer_tier"] = order["customer_tier"]

    return {
        "status": "success",
        "order": order,
        "return_policy_summary": {
            "return_window_days": db.RETURN_WINDOW_DAYS,
            "within_return_window": order["within_return_window"],
            "is_final_sale": order["is_final_sale"],
            "customer_tier": order["customer_tier"],
            "auto_refund_limit_usd": order["auto_refund_limit_usd"],
            "exchange_bonus_credit_usd": db.EXCHANGE_BONUS_CREDIT_USD,
        },
    }


# ---------------------------------------------------------------------------
# 2. Tools for `visual_triage_agent` (Multimodal Gemini Vision)
# ---------------------------------------------------------------------------
def record_damage_assessment(
    order_id: str,
    condition_category: str,
    visual_findings: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Record the visual inspection findings for a returned item in SQLite and session state.

    Args:
        order_id: The order ID being inspected, e.g. 'ORD-1001'.
        condition_category: One of 'unworn_new', 'damaged_in_transit',
            'manufacturing_defect', or 'heavily_used'.
        visual_findings: Concise description of what was observed in the
            customer's photo or claim description.

    Returns:
        A dict with 'status' and the saved inspection report.
    """
    allowed_categories = {
        "unworn_new",
        "damaged_in_transit",
        "manufacturing_defect",
        "heavily_used",
    }
    normalized_category = condition_category.strip().lower()
    if normalized_category not in allowed_categories:
        return {
            "status": "error",
            "error_message": (
                f"Invalid condition_category '{condition_category}'. Must be one of: "
                f"{sorted(allowed_categories)}."
            ),
        }

    # Items that are heavily used / worn with mud or customer-inflicted wear
    # are not eligible for return or exchange.
    eligible_for_return = normalized_category in {
        "unworn_new",
        "damaged_in_transit",
        "manufacturing_defect",
    }

    report = db.log_inspection(
        order_id=order_id,
        condition_category=normalized_category,
        visual_findings=visual_findings,
        eligible_for_return=eligible_for_return,
    )
    tool_context.state["inspection_report"] = report

    return {
        "status": "success",
        "inspection_report": report,
    }


# ---------------------------------------------------------------------------
# 3. Tools for `resolution_agent` (Exchanges, Retention & Refunds)
# ---------------------------------------------------------------------------
def check_exchange_stock(
    product_name: str, tool_context: ToolContext
) -> dict[str, Any]:
    """Check warehouse inventory for available sizes or replacement variants of a product.

    Args:
        product_name: Full or partial product name to search in warehouse stock,
            such as 'TrailBlaze Waterproof Running Shoes' or 'ChronoFit Smart Watch'.

    Returns:
        A dict with 'status', matching SKU variants, stock quantities, and the
        $15 bonus store credit incentive offered for choosing an exchange.
    """
    variants = db.search_inventory_by_product(product_name)
    tool_context.state["last_checked_inventory"] = variants
    return {
        "status": "success",
        "product_query": product_name,
        "exchange_bonus_credit_usd": db.EXCHANGE_BONUS_CREDIT_USD,
        "variants": variants,
    }


def process_exchange(
    order_id: str,
    target_sku: str,
    notes: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Process an instant product exchange, decrement warehouse stock, and grant $15 bonus store credit.

    Args:
        order_id: The verified order ID being exchanged, e.g. 'ORD-1001'.
        target_sku: The replacement SKU from inventory, e.g. 'SKU-SHOE-10'.
        notes: Short summary of the exchange reason (e.g. 'Size swap from Size 9 to Size 10').

    Returns:
        A dict with 'status', exchange confirmation ID, bonus credit, and prepaid return label.
    """
    result = db.create_exchange_resolution(
        order_id=order_id,
        target_sku=target_sku,
        notes=notes,
    )
    if result.get("status") == "success":
        tool_context.state["resolution"] = result
    return result


def issue_refund(
    order_id: str,
    refund_amount_usd: float,
    reason: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Issue a monetary refund for an order and generate a prepaid return label.

    Args:
        order_id: The verified order ID to refund, e.g. 'ORD-1002'.
        refund_amount_usd: Dollar amount to refund (must not exceed order price).
        reason: Reason for the refund (e.g. 'Damaged in transit, replacement out of stock').

    Returns:
        A dict with 'status', refund confirmation ID, refunded amount, and prepaid return label.
    """
    result = db.create_refund_resolution(
        order_id=order_id,
        refund_amount_usd=refund_amount_usd,
        reason=reason,
    )
    if result.get("status") == "success":
        tool_context.state["resolution"] = result
    return result


# ---------------------------------------------------------------------------
# 4. Deterministic Policy Guardrail (`before_tool_callback`)
# ---------------------------------------------------------------------------
def refund_policy_guardrail(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict[str, Any]]:
    """Deterministic `before_tool_callback` protecting exchange and refund tools.

    Returning `None` allows the tool call to proceed normally.
    Returning a `dict` short-circuits the tool call and passes that dict back
    to the LLM as the tool result.
    """
    if tool.name not in {"issue_refund", "process_exchange"}:
        return None

    requested_order_id = str(args.get("order_id", "")).strip().upper()
    active_order = tool_context.state.get("active_order")

    # Guardrail 1: Order must be looked up and match the active session order
    if not active_order or active_order.get("order_id") != requested_order_id:
        order_from_db = db.fetch_order(requested_order_id)
        if not order_from_db:
            return {
                "status": "blocked_by_guardrail",
                "error_message": (
                    f"Guardrail blocked `{tool.name}`: Order '{requested_order_id}' "
                    "has not been verified. Call `lookup_order` first."
                ),
            }
        active_order = order_from_db
        tool_context.state["active_order"] = active_order

    inspection = tool_context.state.get("inspection_report")
    condition = inspection.get("condition_category") if inspection else None

    # Guardrail 2: Block returns/exchanges on heavily worn / customer-damaged items
    if condition == "heavily_used":
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "WEAR_AND_TEAR_EXCLUSION",
            "error_message": (
                f"Guardrail blocked `{tool.name}` for order {requested_order_id}: "
                "Visual inspection classified the item as 'heavily_used' (normal wear, "
                "scuffs, or mud). Items with heavy wear are ineligible for refund or "
                "exchange. Offer the customer courtesy discount code 'LOYALTY10' (10% off)."
            ),
        }

    # Guardrail 3: Enforce 30-day return window (unless damaged in transit)
    days_since_delivery = int(active_order.get("days_since_delivery", 0))
    if (
        days_since_delivery > db.RETURN_WINDOW_DAYS
        and condition != "damaged_in_transit"
    ):
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "RETURN_WINDOW_EXPIRED",
            "error_message": (
                f"Guardrail blocked `{tool.name}` for order {requested_order_id}: "
                f"Order was delivered {days_since_delivery} days ago, exceeding our "
                f"{db.RETURN_WINDOW_DAYS}-day return window. Politely decline the return "
                "and offer courtesy discount code 'LOYALTY10' (10% off next purchase)."
            ),
        }

    # Guardrail 4: Final-sale check (unless damaged in transit or defective)
    if active_order.get("is_final_sale") and condition not in {
        "damaged_in_transit",
        "manufacturing_defect",
    }:
        return {
            "status": "blocked_by_guardrail",
            "policy_rule": "FINAL_SALE_RESTRICTION",
            "error_message": (
                f"Guardrail blocked `{tool.name}`: Order {requested_order_id} is a "
                "Final Sale item and cannot be returned unless damaged in transit."
            ),
        }

    # Guardrail 5: Monetary caps & supervisor escalation for `issue_refund`
    if tool.name == "issue_refund":
        requested_amount = float(args.get("refund_amount_usd", 0.0))
        order_price = float(active_order.get("price_usd", 0.0))
        customer_tier = str(active_order.get("customer_tier", "Standard"))
        tier_limit = float(
            db.AUTO_REFUND_LIMITS_BY_TIER.get(customer_tier, 150.0)
        )

        # Prevent refunding more than the original item price
        if requested_amount > order_price:
            return {
                "status": "blocked_by_guardrail",
                "policy_rule": "EXCEEDS_ORDER_PRICE",
                "error_message": (
                    f"Guardrail blocked `issue_refund`: Requested refund "
                    f"(${requested_amount:.2f}) exceeds the original order price "
                    f"(${order_price:.2f})."
                ),
            }

        # Auto-escalate high-value refunds above the customer's tier cap
        if requested_amount > tier_limit:
            reason = (
                f"Requested refund ${requested_amount:.2f} exceeds automatic approval "
                f"limit of ${tier_limit:.2f} for {customer_tier} tier customers."
            )
            ticket = db.create_escalation_ticket(
                order_id=requested_order_id,
                customer_tier=customer_tier,
                requested_amount_usd=requested_amount,
                tier_limit_usd=tier_limit,
                block_reason=reason,
            )
            tool_context.state["escalation_ticket"] = ticket
            return {
                "status": "escalated_to_supervisor",
                "policy_rule": "HIGH_VALUE_REFUND_ESCALATION",
                "escalation_ticket": ticket,
                "message": (
                    f"Automatic refund of ${requested_amount:.2f} is above the "
                    f"${tier_limit:.2f} auto-approval limit for {customer_tier} tier. "
                    f"Supervisor escalation ticket {ticket['ticket_id']} has been created "
                    "for 2-hour human review."
                ),
            }

    return None


# ---------------------------------------------------------------------------
# 5. Specialist Sub-Agents & Root Coordinator
# ---------------------------------------------------------------------------
order_lookup_agent = Agent(
    name="order_lookup_agent",
    model=MODEL,
    description=(
        "Looks up customer orders by order ID (e.g., ORD-1001), verifies the "
        "30-day return window, and checks customer loyalty tier limits."
    ),
    instruction=(
        "You are the Order & Policy Verification Specialist for ReturnFlow.\n"
        "1. When given an order ID (like ORD-1001), always call `lookup_order`.\n"
        "2. Summarize the item name, variant, purchase price, days since delivery, "
        "customer loyalty tier, and whether the order is within the 30-day return window.\n"
        "3. If the customer also uploaded a photo or described item damage/condition in "
        "the same message, transfer to `visual_triage_agent` after verifying the order.\n"
        "4. If the order is already verified and the customer just wants to know why "
        "they are returning or hasn't uploaded a photo yet, ask them for the return "
        "reason and encourage them to upload a quick photo of the item."
    ),
    tools=[lookup_order],
)

visual_triage_agent = Agent(
    name="visual_triage_agent",
    model=MODEL,
    description=(
        "Inspects customer-uploaded product photos or condition descriptions using "
        "Gemini Vision and logs a structured damage/condition assessment."
    ),
    instruction=(
        "You are the Multimodal Visual Inspection Specialist for ReturnFlow.\n"
        "1. Carefully examine any product photo uploaded by the customer (or their "
        "description if no photo was provided).\n"
        "2. Classify the item's condition into EXACTLY one of these categories:\n"
        "   - `unworn_new`: Brand new, clean, tags/box intact (e.g., wrong size ordered).\n"
        "   - `damaged_in_transit`: Shattered screen, cracked casing, broken on arrival.\n"
        "   - `manufacturing_defect`: Missing parts, stitching defect, hardware failure.\n"
        "   - `heavily_used`: Visible mud, deep wear creases, heavy scuffs from outdoor use.\n"
        "3. Call `record_damage_assessment` with the `order_id`, `condition_category`, "
        "and a clear description of your `visual_findings`.\n"
        "4. Immediately after recording the assessment, transfer to `resolution_agent` "
        "so it can check warehouse inventory for an exchange or process a refund."
    ),
    tools=[record_damage_assessment],
)

resolution_agent = Agent(
    name="resolution_agent",
    model=MODEL,
    description=(
        "Handles exchanges, warehouse inventory checks, $15 bonus retention credits, "
        "refund processing, and supervisor escalations."
    ),
    instruction=(
        "You are the Resolution & Customer Retention Specialist for ReturnFlow.\n"
        "Follow our Retention-First Policy:\n"
        "1. BEFORE issuing a refund for an eligible return (`unworn_new`, "
        "`damaged_in_transit`, or `manufacturing_defect`), ALWAYS call "
        "`check_exchange_stock` for the product name first.\n"
        "2. If the customer wants a different size (e.g. Size 10) or a replacement "
        "and `stock_qty > 0`:\n"
        "   - Pitch an instant exchange that includes a **$15.00 bonus store credit**!\n"
        "   - If the customer already requested the exchange/size swap, call "
        "`process_exchange` right away and share the replacement SKU, warehouse, "
        "$15.00 bonus credit, and prepaid return label code.\n"
        "3. If replacement stock is 0 (out of stock) OR the customer explicitly insists "
        "on a monetary refund instead of an exchange:\n"
        "   - Call `issue_refund` with the order's `order_id` and `price_usd`.\n"
        "4. If `refund_policy_guardrail` blocks or escalates the tool call:\n"
        "   - If `status == 'escalated_to_supervisor'`, empathetically share the "
        "escalation `ticket_id`, explain that their tier's automatic refund limit was "
        "exceeded, and assure them a supervisor will approve it within 2 hours (or "
        "offer an instant exchange with $15 bonus credit if stock is available!).\n"
        "   - If `status == 'blocked_by_guardrail'` due to the 30-day return window or "
        "`heavily_used` condition, explain the policy clearly and offer courtesy "
        "discount code `LOYALTY10` for 10% off their next order."
    ),
    tools=[check_exchange_stock, process_exchange, issue_refund],
    before_tool_callback=refund_policy_guardrail,
)

root_agent = Agent(
    name="returns_concierge",
    model=MODEL,
    description=(
        "Front-desk coordinator for ReturnFlow e-commerce returns, exchanges, "
        "and visual damage claims."
    ),
    instruction=(
        "You are the Front-Desk Coordinator for ReturnFlow, an autonomous e-commerce "
        "returns and exchanges concierge.\n"
        "Route the customer to the right specialist:\n"
        "- If the user provides an order ID (e.g., ORD-1001, ORD-1002, ORD-1003, "
        "ORD-1004, ORD-1005) and the order hasn't been looked up yet, delegate to "
        "`order_lookup_agent`.\n"
        "- If the order is already looked up and the user uploads a product photo "
        "or describes the item's physical condition/damage, delegate to "
        "`visual_triage_agent`.\n"
        "- If the user is asking to check replacement stock, complete a size exchange, "
        "or request a refund, delegate to `resolution_agent`.\n"
        "- If the user greets you without an order ID, welcome them warmly to ReturnFlow "
        "and ask for their Order ID (e.g., ORD-1001 to ORD-1005) and what they need help with."
    ),
    sub_agents=[order_lookup_agent, visual_triage_agent, resolution_agent],
)
