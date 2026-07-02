"""Global app settings (key-value), stored in the app_settings table.

Currently used for the per-meal scheduled-push switch: an operator can turn
breakfast / lunch / dinner scheduled pushes on or off globally to conserve the
LINE push-message quota. Settings persist across restarts. Absent a stored
value, every meal defaults to enabled so existing behaviour is unchanged.

Note: this only gates the SCHEDULED pushes (services.push.push_recommendation
called from the scheduler, which uses push_message and consumes quota). Onboard
and adhoc recommendations reply via reply_token and do not consume push quota,
so they are intentionally never gated here.
"""
import logging

from database import get_conn

logger = logging.getLogger(__name__)

MEAL_TYPES = ("breakfast", "lunch", "dinner")


def _meal_key(meal_type: str) -> str:
    return f"push_enabled:{meal_type}"


def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = CURRENT_TIMESTAMP",
            (key, value),
        )


def is_meal_push_enabled(meal_type: str) -> bool:
    """Default True when no explicit setting exists."""
    value = get_setting(_meal_key(meal_type))
    if value is None:
        return True
    return value == "1"


def set_meal_push_enabled(meal_type: str, enabled: bool) -> None:
    if meal_type not in MEAL_TYPES:
        raise ValueError(f"unknown meal_type: {meal_type}")
    set_setting(_meal_key(meal_type), "1" if enabled else "0")
    logger.info("meal push %s set to %s", meal_type, "on" if enabled else "off")


def all_meal_push_settings() -> dict[str, bool]:
    return {meal: is_meal_push_enabled(meal) for meal in MEAL_TYPES}
