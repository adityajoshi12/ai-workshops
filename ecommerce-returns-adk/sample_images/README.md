# Sample Customer Return Photos for Gemini Multimodal Vision

Upload these sample product photos in the **ADK Web UI (`adk web`)** using the attachment (`+` / paperclip) button when testing the `ReturnFlow` agent:

| File | Order ID | Product | Visual Condition | Expected Triage Outcome |
|---|---|---|---|---|
| `unworn_running_shoes.jpg` | `ORD-1001` | TrailBlaze Waterproof Running Shoes (Size 9) | `unworn_new` - Pristine shoes in original box with retail hangtag attached | Eligible for return/exchange; agent checks warehouse stock for Size 10 (`SKU-SHOE-10`) and offers an instant exchange + **$15.00 bonus store credit**. |
| `cracked_smartwatch.jpg` | `ORD-1002` | ChronoFit Smart Watch | `damaged_in_transit` - Shattered glass screen right out of the retail box | Eligible for return; since replacement stock for `SKU-WATCH-01` is `0`, agent auto-approves a full **$135.00 refund** + prepaid return label. |
| `worn_muddy_boots.jpg` | `ORD-1004` | Alpine Leather Hiking Boots (Size 10) | `heavily_used` - Deep leather creasing, scuffs, and dried mud on soles/uppers | Ineligible for return (`eligible_for_return=False`); guardrail blocks refund/exchange and agent offers a 10% loyalty discount code (`LOYALTY10`). |
