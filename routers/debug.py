"""Manual triggers for diagnosing scheduled-push problems.

All endpoints require an `X-Debug-Secret` header equal to TRACKING_SECRET so
they cannot be hit from the open internet. These are intended for the operator
to verify whether the scheduler / LINE push pipeline actually works without
having to wait for the next cron firing.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Header, HTTPException

from config import TRACKING_SECRET
from scheduler import _all_onboarded_users, _push_to_all

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug")


def _check_secret(secret: Optional[str]) -> None:
    if not secret or secret != TRACKING_SECRET:
        raise HTTPException(status_code=403, detail="forbidden")


@router.get("/users")
def list_users(x_debug_secret: Optional[str] = Header(default=None)):
    """Return the users the scheduler currently considers eligible for push."""
    _check_secret(x_debug_secret)
    return {"users": _all_onboarded_users()}


@router.post("/trigger/{meal_type}")
async def trigger_meal_push(
    meal_type: str,
    x_debug_secret: Optional[str] = Header(default=None),
):
    """Fire `_push_to_all(meal_type)` immediately.

    The endpoint always returns the count of eligible users plus 'ok'. If
    push_message fails for any user, the error is logged but does not surface
    here — tail the server logs to see the actual LINE API response.
    """
    _check_secret(x_debug_secret)
    if meal_type not in {"breakfast", "lunch", "dinner", "supper"}:
        raise HTTPException(status_code=400, detail="invalid meal_type")
    users = _all_onboarded_users()
    logger.info("debug trigger: %s push to %d users", meal_type, len(users))
    await _push_to_all(meal_type)
    return {"status": "ok", "meal_type": meal_type, "eligible_users": len(users)}
