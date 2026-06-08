"""In-memory swap session cache.

Each push builds a weight-ordered candidate list and stores it in a session
keyed by `{line_user_id}:{date}:{meal_type}`. Swaps walk the list in order so
the user never loops back to a restaurant they have already seen. State is lost
on restart, which is acceptable for the POC.
"""
import threading
from dataclasses import dataclass, field
from datetime import datetime

from models import Restaurant

BATCH_SIZE = 3
GUIDANCE_BATCH_THRESHOLD = 2


@dataclass
class SwapSession:
    key: str
    line_user_id: str
    meal_type: str
    origin_lat: float
    origin_lng: float
    is_rainy: bool
    is_adhoc: bool
    candidates: list[Restaurant] = field(default_factory=list)
    index: int = 0
    shown_place_ids: set[str] = field(default_factory=set)
    batch_count: int = 0
    guidance_sent: bool = False

    def next_batch(self, size: int = BATCH_SIZE) -> list[Restaurant]:
        out: list[Restaurant] = []
        while self.index < len(self.candidates) and len(out) < size:
            restaurant = self.candidates[self.index]
            self.index += 1
            if restaurant.place_id in self.shown_place_ids:
                continue
            self.shown_place_ids.add(restaurant.place_id)
            out.append(restaurant)
        return out

    def extend(self, restaurants: list[Restaurant]) -> None:
        for r in restaurants:
            if r.place_id not in self.shown_place_ids:
                self.candidates.append(r)


_lock = threading.Lock()
_sessions: dict[str, SwapSession] = {}
_log_to_key: dict[int, str] = {}
_user_to_key: dict[str, str] = {}


def session_key(line_user_id: str, meal_type: str, is_adhoc: bool) -> str:
    date = datetime.now().strftime("%Y-%m-%d")
    suffix = f"{meal_type}:adhoc" if is_adhoc else meal_type
    return f"{line_user_id}:{date}:{suffix}"


def start_session(
    line_user_id: str,
    meal_type: str,
    origin_lat: float,
    origin_lng: float,
    is_rainy: bool,
    is_adhoc: bool,
    candidates: list[Restaurant],
) -> SwapSession:
    key = session_key(line_user_id, meal_type, is_adhoc)
    session = SwapSession(
        key=key,
        line_user_id=line_user_id,
        meal_type=meal_type,
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        is_rainy=is_rainy,
        is_adhoc=is_adhoc,
        candidates=list(candidates),
    )
    with _lock:
        _sessions[key] = session
        _user_to_key[line_user_id] = key
    return session


def get_session_for_log(push_log_id: int) -> SwapSession | None:
    with _lock:
        key = _log_to_key.get(push_log_id)
        return _sessions.get(key) if key else None


def get_active_session(line_user_id: str) -> SwapSession | None:
    with _lock:
        key = _user_to_key.get(line_user_id)
        return _sessions.get(key) if key else None


def bind_log(push_log_id: int, session: SwapSession) -> None:
    with _lock:
        _log_to_key[push_log_id] = session.key
