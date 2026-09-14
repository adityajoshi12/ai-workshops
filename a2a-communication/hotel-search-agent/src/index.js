import "dotenv/config";
import express from "express";
import { InMemoryTaskStore, DefaultRequestHandler } from "@a2a-js/sdk/server";
import { agentCardHandler, jsonRpcHandler, UserBuilder } from "@a2a-js/sdk/server/express";
import { agentCard, RPC_PATH } from "./agentCard.js";
import { HotelSearchAgentExecutor } from "./executor.js";

const taskStore = new InMemoryTaskStore();
const executor = new HotelSearchAgentExecutor();
const requestHandler = new DefaultRequestHandler(agentCard, taskStore, executor);

const app = express();
app.use(
  `${RPC_PATH}/.well-known/agent-card.json`,
  agentCardHandler({ agentCardProvider: requestHandler })
);
app.use(RPC_PATH, jsonRpcHandler({ requestHandler, userBuilder: UserBuilder.noAuthentication }));

const PORT = process.env.PORT || 8080;
app.listen(PORT, () => {
  console.log(`[hotel-search-agent] listening on http://0.0.0.0:${PORT}`);
  console.log(`[hotel-search-agent] AgentCard: http://0.0.0.0:${PORT}${RPC_PATH}/.well-known/agent-card.json`);
});
