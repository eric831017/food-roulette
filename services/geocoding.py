import logging
from typing import Optional

import httpx

from config import GOOGLE_MAPS_API_KEY

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


async def reverse_geocode(lat: float, lng: float) -> Optional[str]:
    """Reverse-geocode a coordinate to a human-readable district name (zh-TW)."""
    if not GOOGLE_MAPS_API_KEY:
        return None

    params = {
        "latlng": f"{lat},{lng}",
        "language": "zh-TW",
        "result_type": "administrative_area_level_3|administrative_area_level_2|locality",
        "key": GOOGLE_MAPS_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(GEOCODE_URL, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("reverse_geocode failed: %s", e)
        return None

    results = data.get("results") or []
    if not results:
        return None

    # Prefer level_3 (township), then level_2, then locality.
    priority = [
        "administrative_area_level_3",
        "administrative_area_level_2",
        "locality",
    ]
    for kind in priority:
        for result in results:
            for comp in result.get("address_components", []):
                if kind in comp.get("types", []):
                    return comp.get("long_name")
    return results[0].get("formatted_address")
