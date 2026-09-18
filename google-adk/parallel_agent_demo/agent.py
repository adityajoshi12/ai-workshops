"""Demo #4: the Parallel fan-out/fan-in pattern.

    city_briefing (SequentialAgent)
      1. gather (ParallelAgent) - three independent agents run CONCURRENTLY:
           - weather_agent -> state["weather_info"]
           - clock_agent   -> state["time_info"]
           - trivia_agent  -> state["trivia_info"]
      2. synthesizer - reads all three state keys and writes one combined
         answer.

Run `adk web`, pick parallel_agent_demo, and ask:
    "Give me a briefing on Tokyo"
Watch the trace panel: weather_agent, clock_agent, and trivia_agent all fire
at the same timestamp instead of one-after-another - that's the whole point
of ParallelAgent (fan-out for independent work, fan-in to combine results).

Tools are intentionally re-declared here (not imported from my_agent) so
this folder stays a fully standalone `adk run` target, matching every other
demo in this workshop repo.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.tools import google_search

MODEL = "gemini-3.5-flash"

_CITY_TZ = {
    "bengaluru": "Asia/Kolkata",
    "london": "Europe/London",
    "new york": "America/New_York",
    "tokyo": "Asia/Tokyo",
}


def get_weather(city: str) -> dict:
    """Return the current weather for a given city via wttr.in.

    Args:
        city: Name of the city, e.g. "Tokyo".

    Returns:
        {"status": "ok", "city", "weather"} or {"status": "error", "error_message"}.
    """
    try:
        response = requests.get(f"https://wttr.in/{city}?format=3", timeout=10)
        response.raise_for_status()
        return {"status": "ok", "city": city.title(), "weather": response.text.strip()}
    except requests.RequestException as e:
        return {"status": "error", "error_message": f"Failed to fetch weather: {e}"}


def get_current_time(city: str) -> dict:
    """Return the current local time for a given city.

    Args:
        city: Name of the city, e.g. "Tokyo". Must be one of the supported cities.

    Returns:
        {"status": "ok", "city", "current_time"} or {"status": "error", "error_message"}.
    """
    tz_name = _CITY_TZ.get(city.strip().lower())
    if tz_name is None:
        return {
            "status": "error",
            "error_message": f"No timezone for '{city}'. Supported: {', '.join(sorted(_CITY_TZ))}.",
        }
    now = datetime.now(ZoneInfo(tz_name))
    return {"status": "ok", "city": city.title(), "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z")}


weather_agent = Agent(
    name="weather_agent",
    model=MODEL,
    description="Fetches current weather for a city.",
    instruction="Call get_weather for the city in the request and report the result plainly.",
    tools=[get_weather],
    output_key="weather_info",
)

clock_agent = Agent(
    name="clock_agent",
    model=MODEL,
    description="Fetches current local time for a city.",
    instruction="Call get_current_time for the city in the request and report the result plainly.",
    tools=[get_current_time],
    output_key="time_info",
)

trivia_agent = Agent(
    name="trivia_agent",
    model=MODEL,
    description="Finds one fun fact about a city using Google Search.",
    instruction=(
        "Use the google_search tool to find ONE interesting, short fun fact "
        "about the city in the request. Reply with just the fact, one sentence."
    ),
    tools=[google_search],
    output_key="trivia_info",
)

# Fan-out: all three run concurrently since none of them depend on each other.
gather = ParallelAgent(
    name="gather",
    description="Concurrently gathers weather, time, and a fun fact for a city.",
    sub_agents=[weather_agent, clock_agent, trivia_agent],
)

# Fan-in: combines whatever the parallel branch wrote to state.
synthesizer = Agent(
    name="synthesizer",
    model=MODEL,
    description="Combines weather, time, and trivia into one friendly briefing.",
    instruction=(
        "Write a short, friendly city briefing using ONLY the information "
        "below. Do not add facts that aren't present.\n\n"
        "Weather: {weather_info}\n"
        "Local time: {time_info}\n"
        "Fun fact: {trivia_info}"
    ),
)

root_agent = SequentialAgent(
    name="city_briefing",
    description="Gathers weather, time, and trivia in parallel, then writes one briefing.",
    sub_agents=[gather, synthesizer],
)
