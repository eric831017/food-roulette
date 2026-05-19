import base64
import hashlib
import hmac
import json
from typing import Optional

from config import BASE_URL, TRACKING_SECRET
from database import get_conn


def _sign(payload: bytes) -> str:
    sig = hmac.new(TRACKING_SECRET.encode(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig[:8]).decode().rstrip("=")


def encode_tracking_id(push_log_id: int, action: str, **extra) -> str:
    data = {"id": push_log_id, "a": action, **extra}
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    b = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{b}.{_sign(payload)}"


def decode_tracking_id(tracking_id: str) -> Optional[dict]:
    try:
        body, sig = tracking_id.rsplit(".", 1)
        padded = body + "=" * (-len(body) % 4)
        payload = base64.urlsafe_b64decode(padded.encode())
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        return json.loads(payload)
    except Exception:
        return None


def navigate_url_for(push_log_id: int) -> str:
    tid = encode_tracking_id(push_log_id, "navigate")
    return f"{BASE_URL}/r/{tid}"


def phone_url_for(push_log_id: int) -> str:
    tid = encode_tracking_id(push_log_id, "phone")
    return f"{BASE_URL}/r/{tid}"


def log_event(
    line_user_id: str,
    event_type: str,
    push_log_id: Optional[int] = None,
    metadata: Optional[dict] = None,
) -> None:
    meta_str = json.dumps(metadata, ensure_ascii=False) if metadata else None
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (line_user_id, event_type, push_log_id, metadata) "
            "VALUES (?, ?, ?, ?)",
            (line_user_id, event_type, push_log_id, meta_str),
        )
