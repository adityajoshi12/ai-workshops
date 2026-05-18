import * as dotenv from "@dotenvx/dotenvx";
import { tool, createAgent } from "langchain";
import { z } from "zod";

dotenv.config();

const squareTool = tool(
  async ({ n }: { n: number }) => {
    return (n * n).toString();
  },
  {
    name: "square",
    description: "Calculates the square of a number",
    schema: z.object({
      n: z.number().describe("The number to square"),
    }),
  }
);

const weatherTool = tool(
  async ({ city }: { city: string }) => {
    // Fetching real-time weather from wttr.in (returns text format)
    const response = await fetch(`https://wttr.in/${city}?format=3`);
    if (!response.ok) return "Could not fetch weather data.";
    return await response.text();
  },
  {
    name: "get_weather",
    description: "Get the real-time weather for a specific city",
    schema: z.object({
      city: z.string().describe("The city name, e.g., 'London'"),
    }),
  }
);

// Create the agent with multiple tools
const agent = createAgent({
  model: "google:gemini-2.5-flash",
  tools: [squareTool, weatherTool],
});

async function main() {

  const response = await agent.invoke({
    messages: [
      {
        role: "user",
        content: "What is the weather in Tokyo and what is the square of 7?",
      },
    ],
  });

  console.log("Agent:", response.messages[response.messages.length - 1].content);
}

main().catch(console.error);
