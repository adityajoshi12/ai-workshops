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
"""ADK Coding Agent backed by Kubernetes Agent Sandbox."""

import logging
import time

from google.adk.agents.llm_agent import Agent
from k8s_agent_sandbox import SandboxClient

logger = logging.getLogger(__name__)
NAMESPACE = "agent-sandbox-workshop"
WARMPOOL = "workshop-warmpool"

_client = SandboxClient()

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

TEST_ORDER_SERVICE = """\
import unittest
from order_service import calculate_checkout


class OrderServiceTests(unittest.TestCase):
    def test_small_order_adds_shipping(self):
        res = calculate_checkout([{"sku": "BOOK", "price_cents": 2000, "qty": 1}])
        self.assertEqual(res["shipping_cents"], 500)
        self.assertEqual(res["total_cents"], 2500)

    def test_percentage_coupon_applied(self):
        # $40.00 order with 20% off -> $32.00 (3200 cents) + $5.00 shipping = 3700 cents
        res = calculate_checkout(
            [{"sku": "HEADPHONES", "price_cents": 4000, "qty": 1}],
            coupon_pct=20.0,
        )
        self.assertEqual(res["discount_cents"], 800)
        self.assertEqual(res["total_cents"], 3700)

    def test_exact_fifty_dollar_order_gets_free_shipping(self):
        # Exactly 5000 cents ($50.00) after discount must qualify for free shipping (0 cents)
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


def _connect(tenant: str):
    claim_name = f"workshop-{tenant}"
    start = time.monotonic()
    sbx = _client.create_sandbox(
        warmpool=WARMPOOL,
        namespace=NAMESPACE,
        claim_name=claim_name,
        adopt_existing=True,
    )
    elapsed_ms = round((time.monotonic() - start) * 1000, 1)
    pod_name = sbx.get_pod_name()
    logger.info(
        "[AgentSandbox] tenant=%s claim=%s pod=%s container=python-runtime (%sms)",
        tenant,
        claim_name,
        pod_name,
        elapsed_ms,
    )
    return sbx, claim_name, pod_name, elapsed_ms


def claim_sandbox(tenant: str = "alice") -> dict:
    """Claims a pre-warmed sandbox from the GKE WarmPool (or reconnects if already claimed).

    Args:
        tenant: Tenant or session identifier (for example, alice or bob).
    """
    sbx, claim_name, pod_name, elapsed_ms = _connect(tenant)
    kernel = sbx.commands.run("uname -r").stdout.strip()
    return {
        "tenant": tenant,
        "claim_name": claim_name,
        "sandbox_pod": pod_name,
        "container": "python-runtime",
        "claim_latency_ms": elapsed_ms,
        "kernel": kernel,
    }


def seed_buggy_project(tenant: str = "alice") -> dict:
    """Writes the buggy order_service.py and test_order_service.py into the tenant's sandbox.

    Args:
        tenant: Tenant or session identifier (for example, alice).
    """
    sbx, claim_name, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Seeding order_service.py and test_order_service.py", pod_name)
    sbx.files.write("order_service.py", BUGGY_ORDER_SERVICE)
    sbx.files.write("test_order_service.py", TEST_ORDER_SERVICE)
    return {
        "claim_name": claim_name,
        "sandbox_pod": pod_name,
        "seeded_files": ["order_service.py", "test_order_service.py"],
    }


def list_sandbox_files(tenant: str = "alice") -> dict:
    """Lists all files currently in the tenant's sandbox workspace.

    Args:
        tenant: Tenant or session identifier (for example, alice or bob).
    """
    sbx, claim_name, pod_name, _ = _connect(tenant)
    files = sorted(f.name for f in sbx.files.list("."))
    logger.info("[AgentSandbox] [%s] Listed files: %s", pod_name, files)
    return {"claim_name": claim_name, "sandbox_pod": pod_name, "files": files}


def read_sandbox_file(path: str, tenant: str = "alice") -> dict:
    """Reads text content from a file inside the tenant's sandbox.

    Args:
        path: Relative file path in the sandbox workspace (for example, order_service.py).
        tenant: Tenant or session identifier (for example, alice).
    """
    sbx, _, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Reading file '%s'", pod_name, path)
    content = sbx.files.read(path).decode("utf-8")
    return {"sandbox_pod": pod_name, "path": path, "content": content}


def write_sandbox_file(path: str, content: str, tenant: str = "alice") -> dict:
    """Writes text content to a file inside the tenant's sandbox.

    Args:
        path: Relative file path in the sandbox workspace (for example, order_service.py).
        content: Full text content to write to the file.
        tenant: Tenant or session identifier (for example, alice).
    """
    sbx, _, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Writing file '%s'", pod_name, path)
    sbx.files.write(path, content)
    return {"status": "ok", "sandbox_pod": pod_name, "written": path}


def run_in_sandbox(command: str, tenant: str = "alice") -> dict:
    """Runs a shell command or test suite inside the tenant's isolated sandbox.

    Args:
        command: The shell command to run (for example, python3 -m unittest -v test_order_service.py).
        tenant: Tenant or session identifier (for example, alice).
    """
    sbx, _, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Executing command: %s", pod_name, command)
    res = sbx.commands.run(command)
    return {
        "sandbox_pod": pod_name,
        "exit_code": res.exit_code,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }


def check_sandbox_security(tenant: str = "alice") -> dict:
    """Checks the sandbox security boundary: gVisor kernel, non-root user, and blocked GKE metadata server.

    Args:
        tenant: Tenant or session identifier (for example, alice).
    """
    sbx, claim_name, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Running security isolation checks", pod_name)
    kernel = sbx.commands.run("uname -r").stdout.strip()
    user_id = sbx.commands.run("id").stdout.strip()
    probe = (
        "python3 -c \""
        "import urllib.request; "
        "urllib.request.urlopen('http://169.254.169.254', timeout=3)"
        "\""
    )
    ssrf = sbx.commands.run(probe)
    return {
        "status": "ok",
        "claim_name": claim_name,
        "sandbox_pod": pod_name,
        "container": "python-runtime",
        "gvisor_kernel": kernel,
        "process_identity": user_id,
        "metadata_ssrf_blocked": ssrf.exit_code != 0,
    }


def delete_sandbox(tenant: str = "alice") -> dict:
    """Deletes the tenant's SandboxClaim and terminates its backing sandbox pod.

    Args:
        tenant: Tenant or session identifier (for example, alice or bob).
    """
    sbx, claim_name, pod_name, _ = _connect(tenant)
    logger.info("[AgentSandbox] [%s] Terminating claim=%s", pod_name, claim_name)
    sbx.terminate()
    return {"status": "terminated", "claim_name": claim_name, "terminated_pod": pod_name}


root_agent = Agent(
    model="gemini-3.5-flash",
    name="autofix_agent",
    description="Autonomous coding agent that claims Kubernetes Agent Sandboxes, fixes buggy Python projects, and verifies isolation.",
    instruction=(
        "You are an autonomous Python software engineer operating inside Kubernetes Agent Sandboxes. "
        "Every tool takes a tenant name (defaulting to alice) so you can manage isolated sandboxes per user. "
        "Always mention the backing sandbox_pod name, container name, and claim_latency_ms in your responses "
        "so the user can correlate your actions with kubectl get pods."
    ),
    tools=[
        claim_sandbox,
        seed_buggy_project,
        list_sandbox_files,
        read_sandbox_file,
        write_sandbox_file,
        run_in_sandbox,
        check_sandbox_security,
        delete_sandbox,
    ],
)