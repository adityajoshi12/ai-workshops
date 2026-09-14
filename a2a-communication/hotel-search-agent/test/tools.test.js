import { test } from "node:test";
import assert from "node:assert/strict";
import { searchHotels } from "../src/tools.js";

test("search_hotels returns three mock options with the disclaimer", async () => {
  const result = await searchHotels.invoke({
    city: "Austin",
    check_in: "2026-10-03",
    check_out: "2026-10-05",
  });
  assert.equal(result.disclaimer, "MOCK DATA - demo only, not bookable");
  assert.equal(result.options.length, 3);
  for (const option of result.options) {
    assert.equal(option.city, "Austin");
    assert.ok(option.nightly_rate_usd >= 90 && option.nightly_rate_usd < 340);
    assert.ok(option.rating >= 3.5 && option.rating < 5.0);
  }
});

test("search_hotels is deterministic for the same inputs", async () => {
  const a = await searchHotels.invoke({ city: "Austin", check_in: "2026-10-03", check_out: "2026-10-05" });
  const b = await searchHotels.invoke({ city: "Austin", check_in: "2026-10-03", check_out: "2026-10-05" });
  assert.deepEqual(a, b);
});

test("search_hotels varies with different inputs", async () => {
  const a = await searchHotels.invoke({ city: "Austin", check_in: "2026-10-03", check_out: "2026-10-05" });
  const b = await searchHotels.invoke({ city: "Seattle", check_in: "2026-10-03", check_out: "2026-10-05" });
  assert.notDeepEqual(a.options, b.options);
});
