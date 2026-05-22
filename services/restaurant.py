import json
import logging
import math
import random
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import (
    DEDUP_DAYS,
    DEFAULT_RADIUS_M,
    EXPANDED_RADIUS_M,
    GOOGLE_MAPS_API_KEY,
    MIN_POOL_SIZE,
    MIN_RATING,
    RAINY_RADIUS_M,
)
from database import get_conn
from models import Restaurant

logger = logging.getLogger(__name__)

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Static keyword maps. Matches against (zh-TW name + Google types).
MEAL_TYPE_WEIGHTS: dict[str, dict[str, list[str]]] = {
    "breakfast": {
        "boost": [
            "早餐", "早午餐", "豆漿", "brunch", "咖啡", "cafe", "麵包",
            "bakery", "蛋餅", "飯糰", "燒餅", "三明治", "美而美",
        ],
        "exclude": ["火鍋", "燒烤", "燒肉", "串燒", "宵夜", "熱炒", "居酒屋"],
    },
    "lunch": {
        "boost": [
            "便當", "定食", "簡餐", "麵", "飯", "自助餐", "快餐", "丼",
            "lunch_box",
        ],
        "exclude": [],
    },
    "dinner": {
        "boost": [
            "火鍋", "日式", "義式", "義大利", "中式", "韓式", "泰式",
            "燒肉", "牛排", "壽司", "拉麵", "居酒屋", "餐酒館",
        ],
        "exclude": ["早餐", "豆漿"],
    },
}

# Keyword -> human-readable type label (used for storage + analytics).
TYPE_LABELS: list[tuple[str, str]] = [
    ("火鍋", "火鍋"),
    ("燒肉", "燒肉"),
    ("燒烤", "燒烤"),
    ("壽司", "日式"),
    ("拉麵", "日式"),
    ("丼", "日式"),
    ("日式", "日式"),
    ("居酒屋", "日式"),
    ("韓式", "韓式"),
    ("韓國", "韓式"),
    ("泰式", "泰式"),
    ("義大利", "義式"),
    ("義式", "義式"),
    ("披薩", "義式"),
    ("pizza", "義式"),
    ("牛排", "西式"),
    ("漢堡", "西式"),
    ("burger", "西式"),
    ("早午餐", "brunch"),
    ("brunch", "brunch"),
    ("早餐", "早餐"),
    ("豆漿", "早餐"),
    ("麵包", "麵包"),
    ("bakery", "麵包"),
    ("咖啡", "咖啡"),
    ("cafe", "咖啡"),
    ("便當", "便當"),
    ("定食", "便當"),
    ("自助餐", "自助餐"),
    ("快餐", "便當"),
    ("麵", "麵食"),
    ("飯", "中式"),
    ("中式", "中式"),
    ("熱炒", "熱炒"),
]


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return int(2 * r * math.asin(math.sqrt(a)))


def infer_type(name: str, google_types: list[str]) -> str:
    haystack = (name + " " + " ".join(google_types or [])).lower()
    for kw, label in TYPE_LABELS:
        if kw.lower() in haystack:
            return label
    return "其他"


def _match_any(needle_list: list[str], haystack: str) -> bool:
    return any(kw.lower() in haystack for kw in needle_list)


async def fetch_nearby(
    lat: float, lng: float, radius: int
) -> list[dict]:
    if not GOOGLE_MAPS_API_KEY:
        logger.warning("GOOGLE_MAPS_API_KEY not set; returning no candidates.")
        return []

    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": "restaurant",
        "opennow": "true",
        "language": "zh-TW",
        "key": GOOGLE_MAPS_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(NEARBY_URL, params=params)
            r.raise_for_status()
            return r.json().get("results") or []
    except Exception as e:
        logger.warning("nearby search failed: %s", e)
        return []


async def fetch_phone(place_id: str) -> Optional[str]:
    if not GOOGLE_MAPS_API_KEY:
        return None
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number",
        "language": "zh-TW",
        "key": GOOGLE_MAPS_API_KEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(DETAILS_URL, params=params)
            r.raise_for_status()
            return (r.json().get("result") or {}).get("formatted_phone_number")
    except Exception as e:
        logger.warning("place details failed: %s", e)
        return None


def _recently_pushed_place_ids(line_user_id: str, days: int) -> set[str]:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT place_id FROM push_logs "
            "WHERE line_user_id = ? AND pushed_at >= ?",
            (line_user_id, cutoff),
        ).fetchall()
    return {row["place_id"] for row in rows}


def _user_exclusions(line_user_id: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT excluded_type FROM user_exclusions WHERE line_user_id = ?",
            (line_user_id,),
        ).fetchall()
    return {row["excluded_type"] for row in rows}


def _user_blacklist(line_user_id: str) -> set[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT place_id FROM user_blacklist WHERE line_user_id = ?",
            (line_user_id,),
        ).fetchall()
    return {row["place_id"] for row in rows}


def add_blacklist(line_user_id: str, place_id: str, place_name: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_blacklist "
            "(line_user_id, place_id, place_name) VALUES (?, ?, ?)",
            (line_user_id, place_id, place_name),
        )


def navigation_count_7d(place_id: str) -> int:
    """Distinct users who clicked '帶我去' for this place in the past 7 days."""
    cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(DISTINCT pl.line_user_id) AS n
               FROM events e
               JOIN push_logs pl ON pl.id = e.push_log_id
               WHERE e.event_type = 'navigate_click'
                 AND pl.place_id = ? AND e.created_at >= ?""",
            (place_id, cutoff),
        ).fetchone()
    return int(row["n"] or 0)


def _user_preference_boost(line_user_id: str) -> dict[str, float]:
    """Return type -> multiplier based on past accepted recommendations."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT place_type, COUNT(*) AS n FROM push_logs "
            "WHERE line_user_id = ? AND was_accepted = 1 AND is_adhoc = 0 "
            "GROUP BY place_type",
            (line_user_id,),
        ).fetchall()
    if not rows:
        return {}
    total = sum(r["n"] for r in rows) or 1
    return {r["place_type"]: 1.0 + (r["n"] / total) for r in rows}


def _weight_for(
    candidate: dict,
    meal_type: str,
    user_boost: dict[str, float],
) -> float:
    rating = float(candidate.get("rating") or 0.0)
    if rating < MIN_RATING:
        return 0.0
    if not candidate.get("photos"):
        return 0.0

    name = candidate.get("name", "")
    google_types = candidate.get("types") or []
    inferred = infer_type(name, google_types)
    haystack = (name + " " + " ".join(google_types)).lower()

    weights = MEAL_TYPE_WEIGHTS.get(meal_type, {})
    if _match_any(weights.get("exclude", []), haystack):
        return 0.0

    weight = rating  # base
    if _match_any(weights.get("boost", []), haystack):
        weight *= 1.6

    weight *= user_boost.get(inferred, 1.0)
    return weight


def _candidate_to_restaurant(
    candidate: dict, origin_lat: float, origin_lng: float
) -> Restaurant:
    loc = candidate.get("geometry", {}).get("location", {})
    lat = float(loc.get("lat", origin_lat))
    lng = float(loc.get("lng", origin_lng))
    photos = candidate.get("photos") or []
    photo_ref = photos[0].get("photo_reference") if photos else None
    return Restaurant(
        place_id=candidate.get("place_id", ""),
        name=candidate.get("name", ""),
        rating=float(candidate.get("rating") or 0.0),
        lat=lat,
        lng=lng,
        distance_meters=haversine_m(origin_lat, origin_lng, lat, lng),
        price_level=candidate.get("price_level"),
        photo_reference=photo_ref,
        types=candidate.get("types") or [],
        inferred_type=infer_type(candidate.get("name", ""), candidate.get("types") or []),
    )


def _filter_pool(
    candidates: list[dict],
    meal_type: str,
    excluded_ids: set[str],
    excluded_types: set[str],
    blacklist_ids: set[str],
    user_boost: dict[str, float],
) -> list[tuple[dict, float]]:
    pool: list[tuple[dict, float]] = []
    for c in candidates:
        pid = c.get("place_id")
        if pid in excluded_ids or pid in blacklist_ids:
            continue
        inferred = infer_type(c.get("name", ""), c.get("types") or [])
        if inferred in excluded_types:
            continue
        w = _weight_for(c, meal_type, user_boost)
        if w > 0:
            pool.append((c, w))
    return pool


def _weighted_order(pool: list[tuple[dict, float]]) -> list[dict]:
    """Weighted shuffle: higher weight tends to come earlier, order is fixed."""
    items = list(pool)
    ordered: list[dict] = []
    while items:
        weights = [w for _, w in items]
        idx = random.choices(range(len(items)), weights=weights, k=1)[0]
        ordered.append(items.pop(idx)[0])
    return ordered


async def build_candidate_pool(
    line_user_id: str,
    lat: float,
    lng: float,
    meal_type: str,
    is_rainy: bool = False,
    is_adhoc: bool = False,
    exclude_place_ids: Optional[set[str]] = None,
    force_expanded: bool = False,
) -> tuple[list[Restaurant], bool]:
    """Fetch, filter and weight-order nearby restaurants.

    Returns (ordered_restaurants, expanded) where `expanded` indicates the
    expanded search radius was used because the normal pool was too small.
    """
    base_excluded = set(exclude_place_ids or set())
    if not is_adhoc:
        base_excluded |= _recently_pushed_place_ids(line_user_id, DEDUP_DAYS)

    excluded_types = _user_exclusions(line_user_id)
    blacklist_ids = _user_blacklist(line_user_id)
    user_boost = {} if is_adhoc else _user_preference_boost(line_user_id)

    base_radius = RAINY_RADIUS_M if is_rainy else DEFAULT_RADIUS_M
    radius = EXPANDED_RADIUS_M if force_expanded else base_radius
    expanded = force_expanded

    candidates = await fetch_nearby(lat, lng, radius)
    pool = _filter_pool(
        candidates, meal_type, base_excluded, excluded_types,
        blacklist_ids, user_boost,
    )

    # Dynamic radius expansion when the filtered pool is too small.
    if len(pool) < MIN_POOL_SIZE and not expanded:
        expanded_candidates = await fetch_nearby(lat, lng, EXPANDED_RADIUS_M)
        if expanded_candidates:
            expanded_pool = _filter_pool(
                expanded_candidates, meal_type, base_excluded, excluded_types,
                blacklist_ids, user_boost,
            )
            if len(expanded_pool) > len(pool):
                candidates, pool, expanded = expanded_candidates, expanded_pool, True

    if not pool:
        # Fallback: relax dedup but still honour explicit exclusions/blacklist.
        relaxed_excluded = set(exclude_place_ids or set())
        pool = _filter_pool(
            candidates, meal_type, relaxed_excluded, excluded_types,
            blacklist_ids, user_boost,
        )

    ordered = _weighted_order(pool)
    return [_candidate_to_restaurant(c, lat, lng) for c in ordered], expanded


def record_push(
    line_user_id: str,
    restaurant: Restaurant,
    meal_type: str,
    weather_condition: str,
    is_adhoc: bool,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO push_logs
               (line_user_id, place_id, place_name, place_type, place_rating,
                place_lat, place_lng, distance_meters, meal_type, is_adhoc,
                weather_condition)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                line_user_id,
                restaurant.place_id,
                restaurant.name,
                restaurant.inferred_type,
                restaurant.rating,
                restaurant.lat,
                restaurant.lng,
                restaurant.distance_meters,
                meal_type,
                1 if is_adhoc else 0,
                weather_condition,
            ),
        )
        return cur.lastrowid


def increment_swap(push_log_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE push_logs SET swap_count = swap_count + 1 WHERE id = ?",
            (push_log_id,),
        )


def mark_accepted(push_log_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE push_logs SET was_accepted = 1 WHERE id = ?",
            (push_log_id,),
        )


def get_push_log(push_log_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM push_logs WHERE id = ?", (push_log_id,)
        ).fetchone()
    return row
