import logging
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from services.restaurant import get_push_log, mark_accepted
from services.tracking import decode_tracking_id, log_event

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/r/{tracking_id}")
def redirect_handler(tracking_id: str):
    payload = decode_tracking_id(tracking_id)
    if not payload:
        raise HTTPException(status_code=404, detail="invalid tracking id")

    push_log_id = int(payload.get("id", 0))
    action = payload.get("a")
    row = get_push_log(push_log_id)
    if not row:
        raise HTTPException(status_code=404, detail="push log not found")

    if action == "navigate":
        mark_accepted(push_log_id)
        log_event(row["line_user_id"], "navigate_click", push_log_id=push_log_id)
        query = quote(row["place_name"] or f"{row['place_lat']},{row['place_lng']}")
        url = (
            "https://www.google.com/maps/search/?api=1"
            f"&query={query}&query_place_id={row['place_id']}"
        )
        return RedirectResponse(url=url, status_code=302)

    if action == "phone":
        log_event(row["line_user_id"], "phone_click", push_log_id=push_log_id)
        phone = payload.get("p") or ""
        return RedirectResponse(url=f"tel:{phone}", status_code=302)

    if action == "ig":
        log_event(row["line_user_id"], "ig_click", push_log_id=push_log_id)
        query = quote(row["place_name"] or "")
        url = f"https://www.instagram.com/explore/search/keyword/?q={query}"
        return RedirectResponse(url=url, status_code=302)

    raise HTTPException(status_code=400, detail="unknown action")
