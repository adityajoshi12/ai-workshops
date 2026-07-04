"""Demo #1: a single agent with tools (the ADK 'hello world').

One agent, two function tools. Run `adk web`, pick my_agent, and ask a
weather or time question. The whole point of the demo is to watch the model
DECIDE which tool to call in the trace panel - that decision is the agent.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from google.adk.agents import Agent

# Centralized so you can swap the model in one place.
MODEL = "gemini-3.5-flash"

# A tiny fake "weather service". In a real agent this would hit a live API;
# hardcoded data keeps the demo offline-friendly and deterministic.
_WEATHER_DB = {
    "bengaluru": {"temp_c": 29, "sky": "clear", "humidity_pct": 55},
    "london": {"temp_c": 14, "sky": "overcast", "humidity_pct": 80},
    "new york": {"temp_c": 22, "sky": "partly cloudy", "humidity_pct": 60},
    "tokyo": {"temp_c": 26, "sky": "light rain", "humidity_pct": 90},
}
_CITY_TZ = {
    "bengaluru": "Asia/Kolkata",
    "london": "Europe/London",
    "new york": "America/New_York",
    "tokyo": "Asia/Tokyo",
}


import requests


def get_weather(city: str) -> dict:
    """Return the current weather for a given city.

    Args:
        city: Name of the city, e.g. "Bengaluru". Case-insensitive.

    Returns:
        On success:
            {
                "status": "ok",
                "city": "<City>",
                "weather": "<weather summary>"
            }

        On failure:
            {
                "status": "error",
                "error_message": "<error details>"
            }
    """
    try:
        url = f"https://wttr.in/{city}?format=3"
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        return {
            "status": "ok",
            "city": city.title(),
            "weather": response.text.strip(),
        }

    except requests.RequestException as e:
        return {
            "status": "error",
            "error_message": f"Failed to fetch weather: {e}",
        }


def get_current_time(city: str) -> dict:
    """Return the current local time for a given city.

    Args:
        city: Name of the city, e.g. "Tokyo". Case-insensitive.

    Returns:
        On success: {"status": "ok", "city", "current_time"}.
        On failure: {"status": "error", "error_message"} when the city is
        not in the supported list.
    """
    tz_name = _CITY_TZ.get(city.strip().lower())
    if tz_name is None:
        return {
            "status": "error",
            "error_message": (
                f"No timezone for '{city}'. "
                f"Supported cities: {', '.join(sorted(_CITY_TZ))}."
            ),
        }
    now = datetime.now(ZoneInfo(tz_name))
    return {
        "status": "ok",
        "city": city.title(),
        "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


root_agent = Agent(
    model=MODEL,
    name="root_agent",
    description="A helpful assistant that answers weather and time questions.",
    instruction=(
        "You are a friendly assistant. "
        "Use the get_weather tool for weather questions and the "
        "get_current_time tool for time questions. "
        "If a tool returns status 'error', apologize and pass along the "
        "error_message so the user knows which cities are supported. "
        "Never invent weather or time data - always call a tool."
    ),
    tools=[get_weather, get_current_time],
)
