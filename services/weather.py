import logging
from typing import Optional

import httpx

from config import OPENWEATHERMAP_API_KEY

logger = logging.getLogger(__name__)

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"


async def get_weather(lat: float, lng: float) -> dict:
    """Return {'condition': str, 'is_rainy': bool, 'temp_c': float|None}."""
    if not OPENWEATHERMAP_API_KEY:
        return {"condition": "unknown", "is_rainy": False, "temp_c": None}

    params = {
        "lat": lat,
        "lon": lng,
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric",
        "lang": "zh_tw",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(OWM_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("get_weather failed: %s", e)
        return {"condition": "unknown", "is_rainy": False, "temp_c": None}

    weather = (data.get("weather") or [{}])[0]
    main = (weather.get("main") or "").lower()
    is_rainy = main in {"rain", "drizzle", "thunderstorm"}
    return {
        "condition": weather.get("main", "unknown"),
        "is_rainy": is_rainy,
        "temp_c": (data.get("main") or {}).get("temp"),
    }


def get_weather_sync(lat: float, lng: float) -> dict:
    """Sync wrapper for the scheduler thread."""
    import asyncio

    return asyncio.run(get_weather(lat, lng))
