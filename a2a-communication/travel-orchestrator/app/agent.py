# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

import google.adk.agents.remote_a2a_agent as ra
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

# Allow plain HTTP endpoints for demo / direct IP targets
ra._is_loopback_host = lambda host: True


MODEL = "gemini-3.7-flash"

# Base URLs of the two remote specialists - point these at wherever each is
# actually running (localhost for local dev, or the deployed GKE/VM address).
# The "/a2a/app" segment matches the rpc_path every adk_a2a scaffold uses
# (App(name="app") -> rpc_path=f"/a2a/{app.name}").
FLIGHT_AGENT_URL = os.environ.get("FLIGHT_AGENT_URL", "http://localhost:8001")
HOTEL_AGENT_URL = os.environ.get("HOTEL_AGENT_URL", "http://localhost:8002")

flight_agent = RemoteA2aAgent(
    name="flight_search_agent",
    description="Searches mock flight options between an origin and destination.",
    agent_card=f"{FLIGHT_AGENT_URL}/a2a/app{AGENT_CARD_WELL_KNOWN_PATH}",
)

hotel_agent = RemoteA2aAgent(
    name="hotel_search_agent",
    description="Searches mock hotel options in a city for a date range.",
    agent_card=f"{HOTEL_AGENT_URL}/a2a/app{AGENT_CARD_WELL_KNOWN_PATH}",
)

root_agent = Agent(
    name="travel_orchestrator",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a travel planning orchestrator. For any trip request, delegate "
        "flight questions to flight_search_agent and hotel questions to "
        "hotel_search_agent (both are remote agents reached over A2A), then "
        "combine their answers into one itinerary. Always disclose this is mock "
        "demo data - nothing here is bookable."
    ),
    sub_agents=[flight_agent, hotel_agent],
)

app = App(
    root_agent=root_agent,
    name="app",
)
