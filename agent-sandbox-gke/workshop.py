#!/usr/bin/env python3
# Copyright 2026 The Kubernetes Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""GKE Agent Platform Workshop — Coding Agent on Agent Sandbox.

Four short commands that show the full Sandbox lifecycle with the Python SDK:

  python3 workshop.py seed             # 1. Claim warm sandbox, write buggy order service, run tests (3 FAIL)
  python3 workshop.py fix              # 2. Re-adopt same sandbox, patch the 3 bugs, run tests (4 OK)
  python3 workshop.py check-security   # 3. Verify gVisor kernel, non-root user & blocked metadata SSRF
  python3 workshop.py cleanup          # 4. Delete the SandboxClaim and terminate the sandbox pod
"""

import argparse
import time

from k8s_agent_sandbox import SandboxClient

NAMESPACE = "agent-sandbox-workshop"
WARMPOOL = "workshop-warmpool"

BUGGY_ORDER_SERVICE = """\
\"\"\"Order checkout calculator with 3 bugs for the agent to diagnose and fix.\"\"\"


def calculate_checkout(items: list[dict], coupon_pct: float = 0.0) -> dict:
    \"\"\"Compute subtotal, discount, shipping, and total (all in cents).

    Rules:
      - Each item is {"sku": str, "price_cents": int, "qty": int}.
      - Reject non-positive quantities (qty <= 0) or negative prices with ValueError.
      - coupon_pct (0..100) reduces the subtotal, rounded to nearest cent.
      - Shipping is 500 cents ($5.00), or FREE (0 cents) when discounted subtotal >= 5000 cents ($50.00).
    \"\"\"
    subtotal = 0
    for item in items:
        if item["price_cents"] < 0:
            raise ValueError("price_cents cannot be negative")
        # BUG 1: Missing validation for item["qty"] <= 0
        subtotal += item["price_cents"] * item["qty"]

    # BUG 2: Integer floor division (//) zeroes out any coupon_pct < 100
    discount = round(subtotal * (coupon_pct // 100))
    discounted_subtotal = subtotal - discount

    # BUG 3: Off-by-one (> 5000 instead of >= 5000) charges shipping on exact $50.00 orders
    shipping = 0 if discounted_subtotal > 5000 else 500

    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "shipping_cents": shipping,
        "total_cents": discounted_subtotal + shipping,
    }
"""

FIXED_ORDER_SERVICE = """\
\"\"\"Order checkout calculator with all 3 bugs fixed.\"\"\"


def calculate_checkout(items: list[dict], coupon_pct: float = 0.0) -> dict:
    subtotal = 0
    for item in items:
        if item["price_cents"] < 0:
            raise ValueError("price_cents cannot be negative")
        if item["qty"] <= 0:
            raise ValueError("qty must be positive")
        subtotal += item["price_cents"] * item["qty"]

    discount = round(subtotal * (coupon_pct / 100.0))
    discounted_subtotal = subtotal - discount
    shipping = 0 if discounted_subtotal >= 5000 else 500

    return {
        "subtotal_cents": subtotal,
        "discount_cents": discount,
        "shipping_cents": shipping,
        "total_cents": discounted_subtotal + shipping,
    }
"""

TEST_ORDER_SERVICE = """\
import unittest
from order_service import calculate_checkout


class OrderServiceTests(unittest.TestCase):
    def test_small_order_adds_shipping(self):
        res = calculate_checkout([{"sku": "BOOK", "price_cents": 2000, "qty": 1}])
        self.assertEqual(res["shipping_cents"], 500)
        self.assertEqual(res["total_cents"], 2500)

    def test_percentage_coupon_applied(self):
        res = calculate_checkout(
            [{"sku": "HEADPHONES", "price_cents": 4000, "qty": 1}],
            coupon_pct=20.0,
        )
        self.assertEqual(res["discount_cents"], 800)
        self.assertEqual(res["total_cents"], 3700)

    def test_exact_fifty_dollar_order_gets_free_shipping(self):
        res = calculate_checkout([{"sku": "KEYBOARD", "price_cents": 2500, "qty": 2}])
        self.assertEqual(res["shipping_cents"], 0)
        self.assertEqual(res["total_cents"], 5000)

    def test_rejects_negative_or_zero_quantity(self):
        with self.assertRaises(ValueError):
            calculate_checkout([{"sku": "EXPLOIT", "price_cents": 1000, "qty": -2}])
        with self.assertRaises(ValueError):
            calculate_checkout([{"sku": "ZERO", "price_cents": 1000, "qty": 0}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
"""


def get_sandbox(client: SandboxClient, tenant: str):
    """Claim a warm sandbox (or reconnect to it if it already exists)."""
    claim_name = f"workshop-{tenant}"
    start = time.monotonic()
    sandbox = client.create_sandbox(
        warmpool=WARMPOOL,
        namespace=NAMESPACE,
        claim_name=claim_name,
        adopt_existing=True,
    )
    elapsed = time.monotonic() - start
    print(
        f"==> Connected to claim='{claim_name}' "
        f"pod='{sandbox.get_pod_name()}' (container=python-runtime) in {elapsed:.2f}s"
    )
    return sandbox


def cmd_seed(sandbox) -> None:
    """Step 1: Write buggy order_service.py and unit tests into the sandbox, then run them."""
    sandbox.files.write("order_service.py", BUGGY_ORDER_SERVICE)
    sandbox.files.write("test_order_service.py", TEST_ORDER_SERVICE)
    print(f"==> [{sandbox.get_pod_name()}] Wrote order_service.py (buggy) and test_order_service.py")

    res = sandbox.commands.run("python3 -m unittest -v test_order_service.py")
    print(res.stdout + res.stderr)


def cmd_fix(sandbox) -> None:
    """Step 2: Patch the 3 bugs in the existing sandbox and re-run the unit tests."""
    pod = sandbox.get_pod_name()
    print(f"==> [{pod}] Current files in sandbox:", [f.name for f in sandbox.files.list(".")])
    sandbox.files.write("order_service.py", FIXED_ORDER_SERVICE)
    print(f"==> [{pod}] Patched order_service.py")

    res = sandbox.commands.run("python3 -m unittest -v test_order_service.py")
    print(res.stdout + res.stderr)


def cmd_check_security(sandbox) -> None:
    """Step 3: Verify gVisor kernel, non-root user, and blocked metadata server."""
    pod = sandbox.get_pod_name()
    print(f"==> [{pod}] 1. Kernel version inside sandbox (gVisor virtualized kernel):")
    print("   ", sandbox.commands.run("uname -r").stdout.strip())

    print(f"==> [{pod}] 2. Process identity (non-root user):")
    print("   ", sandbox.commands.run("id").stdout.strip())

    print(f"==> [{pod}] 3. Probing GKE Metadata Server (169.254.169.254) — blocked by SandboxTemplate NetworkPolicy:")
    probe = (
        "python3 -c \""
        "import urllib.request; "
        "urllib.request.urlopen('http://169.254.169.254', timeout=3)"
        "\""
    )
    res = sandbox.commands.run(probe)
    if res.exit_code != 0:
        print("    BLOCKED (as expected): connection timed out / unreachable")
    else:
        print("    WARNING: metadata server was reachable!")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=["seed", "fix", "check-security", "cleanup"])
    parser.add_argument("--tenant", default="alice", help="Tenant name (default: alice)")
    args = parser.parse_args()

    client = SandboxClient()
    sandbox = get_sandbox(client, args.tenant)

    if args.step == "seed":
        cmd_seed(sandbox)
    elif args.step == "fix":
        cmd_fix(sandbox)
    elif args.step == "check-security":
        cmd_check_security(sandbox)
    elif args.step == "cleanup":
        pod = sandbox.get_pod_name()
        sandbox.terminate()
        print(f"==> Terminated claim 'workshop-{args.tenant}' (pod '{pod}')")


if __name__ == "__main__":
    main()

