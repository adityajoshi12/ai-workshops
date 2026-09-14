// AgentCard advertised at /a2a/app/.well-known/agent-card.json.
// Field shape mirrors the A2A v1.0 spec (same shape the other two agents'
// ADK-generated cards use) so travel-orchestrator's RemoteA2aAgent needs
// zero changes to talk to this rewritten agent.

import { A2A_PROTOCOL_VERSION } from "@a2a-js/sdk";

const APP_URL = process.env.APP_URL || "http://0.0.0.0:8080";
export const RPC_PATH = "/a2a/app";

export const agentCard = {
  name: "hotel_search_agent",
  description: "Searches mock hotel options in a city for a date range.",
  supportedInterfaces: [
    {
      url: `${APP_URL}${RPC_PATH}`,
      protocolBinding: "JSONRPC",
      tenant: "",
      protocolVersion: A2A_PROTOCOL_VERSION,
    },
  ],
  provider: {
    organization: "A2A Cross-Platform Demo",
    url: "https://github.com/a2aproject/A2A",
  },
  version: process.env.AGENT_VERSION || "0.1.0",
  capabilities: {
    streaming: true,
    pushNotifications: false,
    extensions: [],
    extendedAgentCard: false,
  },
  // Unauthenticated, on purpose, same caveat as the rest of this demo -
  // see the "What This Demo Skips on Purpose" slide in the deck.
  securitySchemes: {},
  securityRequirements: [],
  defaultInputModes: ["text"],
  defaultOutputModes: ["text", "task-status"],
  skills: [
    {
      id: "search_hotels",
      name: "Search Hotels",
      description:
        "Find hotel options for a city + check-in/check-out date range.",
      tags: ["travel", "hotels", "demo"],
      examples: ["Find hotels in Austin, Oct 3-5"],
      inputModes: ["text"],
      outputModes: ["text", "task-status"],
      securityRequirements: [],
    },
  ],
  documentationUrl: "",
  signatures: [],
};
