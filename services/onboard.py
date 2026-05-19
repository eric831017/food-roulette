from typing import Optional

from database import get_conn


def get_user(line_user_id: str) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE line_user_id = ?", (line_user_id,)
        ).fetchone()
    return dict(row) if row else None


def ensure_user(line_user_id: str, display_name: Optional[str] = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (line_user_id, display_name) VALUES (?, ?)",
            (line_user_id, display_name),
        )


def reset_user(line_user_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """UPDATE users
               SET location_1_lat = NULL, location_1_lng = NULL, location_1_name = NULL,
                   location_2_lat = NULL, location_2_lng = NULL, location_2_name = NULL,
                   onboard_complete = 0
               WHERE line_user_id = ?""",
            (line_user_id,),
        )


def set_location(
    line_user_id: str, slot: int, lat: float, lng: float, name: Optional[str]
) -> None:
    if slot not in (1, 2):
        raise ValueError("slot must be 1 or 2")
    cols = {
        1: ("location_1_lat", "location_1_lng", "location_1_name"),
        2: ("location_2_lat", "location_2_lng", "location_2_name"),
    }[slot]
    with get_conn() as conn:
        conn.execute(
            f"UPDATE users SET {cols[0]} = ?, {cols[1]} = ?, {cols[2]} = ? "
            f"WHERE line_user_id = ?",
            (lat, lng, name, line_user_id),
        )


def next_empty_slot(user: dict) -> Optional[int]:
    if user.get("location_1_lat") is None:
        return 1
    if user.get("location_2_lat") is None:
        return 2
    return None


def mark_onboard_complete(line_user_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET onboard_complete = 1 WHERE line_user_id = ?",
            (line_user_id,),
        )


def add_exclusion(line_user_id: str, excluded_type: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO user_exclusions (line_user_id, excluded_type) "
            "VALUES (?, ?)",
            (line_user_id, excluded_type),
        )


def pick_anchor_location(user: dict, when_iso_weekday: int) -> Optional[tuple[float, float]]:
    """when_iso_weekday: 1=Mon..7=Sun. Weekends use location_2 if set."""
    use_loc_2 = when_iso_weekday in (6, 7) and user.get("location_2_lat") is not None
    if use_loc_2:
        return user["location_2_lat"], user["location_2_lng"]
    if user.get("location_1_lat") is not None:
        return user["location_1_lat"], user["location_1_lng"]
    return None
