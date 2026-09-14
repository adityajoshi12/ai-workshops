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

import hashlib

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types


MODEL = "gemini-3.7-flash"

_AIRLINES = ["Puppy Air", "Kennel Express", "Fetch Airways"]


def search_flights(origin: str, destination: str, date: str) -> dict:
    """Searches mock flight options between two airports on a given date.

    DEMO DATA ONLY - no real flights, no booking capability.

    Args:
        origin: Origin airport code or city (e.g. "SFO").
        destination: Destination airport code or city (e.g. "AUS").
        date: Travel date, e.g. "2026-10-03".

    Returns:
        A dict with a list of illustrative flight options.
    """
    seed = int(hashlib.sha256(f"{origin}{destination}{date}".encode()).hexdigest(), 16)
    options = []
    for i, airline in enumerate(_AIRLINES):
        price = 120 + ((seed >> (i * 4)) % 300)
        depart_hour = 6 + ((seed >> (i * 3)) % 14)
        options.append(
            {
                "airline": airline,
                "flight_number": f"{airline[:2].upper()}{100 + i}",
                "origin": origin,
                "destination": destination,
                "date": date,
                "depart_time": f"{depart_hour:02d}:00",
                "price_usd": price,
            }
        )
    return {"disclaimer": "MOCK DATA - demo only, not bookable", "options": options}


root_agent = Agent(
    name="flight_search_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a flight search specialist. Use search_flights to find options "
        "between an origin and destination on a given date, then summarize the "
        "cheapest and fastest choices. Always disclose this is mock demo data."
    ),
    tools=[search_flights],
)

app = App(
    root_agent=root_agent,
    name="app",
)
