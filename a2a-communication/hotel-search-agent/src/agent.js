// LangGraph.js agent via LangChain's current `createAgent` (the
// `@langchain/langgraph/prebuilt` `createReactAgent` this replaces is
// deprecated upstream - see langchain's own JSDoc pointing at this API).

import { createAgent } from "langchain";
import { ChatVertexAI } from "@langchain/google-vertexai";
import { searchHotels } from "./tools.js";

const MODEL = process.env.MODEL_NAME || "gemini-3.7-flash";

const llm = new ChatVertexAI({
  model: MODEL,
  temperature: 0,
  project: process.env.GOOGLE_CLOUD_PROJECT,
  location: process.env.GOOGLE_CLOUD_LOCATION || "global",
});

export const hotelAgent = createAgent({
  model: llm,
  tools: [searchHotels],
  prompt:
    "You are a hotel search specialist. Use search_hotels to find options " +
    "in a city for a check-in/check-out range, then summarize the best " +
    "value and highest-rated choices. Always disclose this is mock demo data.",
});

/** Runs the agent on a single text query, returns the final answer text. */
export async function runHotelAgent(query) {
  const result = await hotelAgent.invoke({
    messages: [{ role: "user", content: query }],
  });
  const last = result.messages.at(-1);
  const content = last?.content;
  if (typeof content === "string") return content;
  // Some providers return content as an array of parts - flatten to text.
  if (Array.isArray(content)) {
    return content
      .map((part) => (typeof part === "string" ? part : part.text ?? ""))
      .join("");
  }
  return String(content ?? "");
}
