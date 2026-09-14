// Same mock hotel data and deterministic pseudo-random pricing as the
// original Python/LangGraph version this replaces - port, not a rewrite of
// the demo's behavior.

import { createHash } from "node:crypto";
import { tool } from "langchain";
import { z } from "zod";

const HOTELS = ["Bark Suites", "The Doghouse Inn", "Golden Retriever Grand"];

function seededInt(input) {
  const hex = createHash("sha256").update(input).digest("hex");
  return BigInt(`0x${hex}`);
}

export const searchHotels = tool(
  ({ city, check_in: checkIn, check_out: checkOut }) => {
    const seed = seededInt(`${city}${checkIn}${checkOut}`);
    const options = HOTELS.map((hotel, i) => {
      const shift = BigInt(i * 5);
      const nightly = 90 + Number((seed >> shift) % 250n);
      const ratingShift = BigInt(i * 2);
      const rating = 3.5 + Number((seed >> ratingShift) % 15n) / 10;
      return {
        hotel,
        city,
        check_in: checkIn,
        check_out: checkOut,
        nightly_rate_usd: nightly,
        rating: Math.round(rating * 10) / 10,
      };
    });
    return { disclaimer: "MOCK DATA - demo only, not bookable", options };
  },
  {
    name: "search_hotels",
    description:
      "Searches mock hotel options in a city for a date range. " +
      "DEMO DATA ONLY - no real hotels, no booking capability.",
    schema: z.object({
      city: z.string().describe('City to search hotels in (e.g. "Austin").'),
      check_in: z.string().describe('Check-in date, e.g. "2026-10-03".'),
      check_out: z.string().describe('Check-out date, e.g. "2026-10-05".'),
    }),
  }
);
