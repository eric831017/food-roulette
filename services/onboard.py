import threading
from typing import Optional

from database import get_conn


_pending_reset: set[str] = set()
_pending_lock = threading.Lock()


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
                   onboard_complete = 0
               WHERE line_user_id = ?""",
            (line_user_id,),
        )


def set_location(
    line_user_id: str, lat: float, lng: float, name: Optional[str]
) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET location_1_lat = ?, location_1_lng = ?, location_1_name = ? "
            "WHERE line_user_id = ?",
            (lat, lng, name, line_user_id),
        )


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


def pick_anchor_location(user: dict) -> Optional[tuple[float, float]]:
    if user.get("location_1_lat") is not None:
        return user["location_1_lat"], user["location_1_lng"]
    return None


def mark_pending_reset(line_user_id: str) -> None:
    with _pending_lock:
        _pending_reset.add(line_user_id)


def consume_pending_reset(line_user_id: str) -> bool:
    with _pending_lock:
        if line_user_id in _pending_reset:
            _pending_reset.discard(line_user_id)
            return True
        return False
