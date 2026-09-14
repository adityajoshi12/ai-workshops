# hotel-search-agent runs on Node/LangGraph.js, unlike the other two agents
# in this demo (Python/ADK) - deliberately, to prove the A2A wire protocol
# is framework- and language-neutral, not just cross-platform.

FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json* ./
ENV NODE_OPTIONS=--max-old-space-size=512
RUN npm ci --omit=dev
ENV NODE_OPTIONS=

COPY src ./src

ARG AGENT_VERSION=0.0.0
ENV AGENT_VERSION=${AGENT_VERSION}

EXPOSE 8080

CMD ["node", "src/index.js"]
