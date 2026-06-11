import logging
from typing import Optional

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexContainer,
    FlexMessage,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from config import LINE_CHANNEL_ACCESS_TOKEN
from flex_messages.daily_push import (
    build_alt_text_carousel,
    build_daily_bubble,
    build_daily_carousel,
    build_swap_batch_bubble,
)
from flex_messages.weekly_digest import build_weekly_carousel
from models import Restaurant
from services.analytics import weekly_stats
from services.onboard import get_user, pick_anchor_location
from services.restaurant import (
    build_candidate_pool,
    navigation_count_7d,
    record_push,
)
from services.session import (
    GUIDANCE_BATCH_THRESHOLD,
    SwapSession,
    bind_log,
    get_active_session,
    start_session,
)
from services.tracking import log_event
from services.weather import get_weather

logger = logging.getLogger(__name__)

EXHAUSTED_MSG = (
    "今天附近的選項都看過了 😅 傳一個新位置給我，"
    "或是等下一餐讓我重新幫你找！"
)
SWAP_GUIDANCE_MSG = (
    "附近的選項似乎都不太合胃口？傳一個位置給我，我幫你找更遠的好店 🗺️"
)
NO_CANDIDATES_MSG = "這附近找不到合適的餐廳，再試試其他地點吧。"


def _api() -> MessagingApi:
    cfg = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    return MessagingApi(ApiClient(cfg))


def flex_message_from_dict(alt_text: str, contents: dict) -> FlexMessage:
    return FlexMessage(altText=alt_text, contents=FlexContainer.from_dict(contents))


def _build_carousel_messages(
    batch: list[Restaurant],
    log_ids: list[int],
    meal_type: str,
    expanded: bool,
) -> list[FlexMessage]:
    bubbles = [
        build_daily_bubble(
            r, log_id, meal_type,
            expanded=expanded,
            social_count=navigation_count_7d(r.place_id),
            is_top_pick=(i == 0),
        )
        for i, (r, log_id) in enumerate(zip(batch, log_ids))
    ]
    carousel = flex_message_from_dict(
        build_alt_text_carousel(batch, meal_type),
        build_daily_carousel(bubbles),
    )
    swap_control = flex_message_from_dict("換一批", build_swap_batch_bubble())
    return [carousel, swap_control]


def _record_batch(
    line_user_id: str,
    batch: list[Restaurant],
    meal_type: str,
    weather_condition: str,
    is_adhoc: bool,
    session: SwapSession,
) -> list[int]:
    log_ids = []
    for r in batch:
        log_id = record_push(line_user_id, r, meal_type, weather_condition, is_adhoc)
        bind_log(log_id, session)
        log_ids.append(log_id)
    return log_ids


def _send(
    reply_token: Optional[str],
    line_user_id: str,
    messages: list,
) -> None:
    if reply_token:
        _api().reply_message(ReplyMessageRequest(
            replyToken=reply_token, messages=messages,
        ))
    else:
        _api().push_message(PushMessageRequest(
            to=line_user_id, messages=messages,
        ))


async def push_recommendation(
    line_user_id: str, meal_type: str, is_adhoc: bool = False,
    adhoc_lat: Optional[float] = None, adhoc_lng: Optional[float] = None,
    reply_token: Optional[str] = None,
    prefix_messages: Optional[list] = None,
) -> bool:
    user = get_user(line_user_id)
    if not user and not is_adhoc:
        logger.info("push skipped: no user %s", line_user_id)
        return False

    if is_adhoc:
        if adhoc_lat is None or adhoc_lng is None:
            return False
        lat, lng = adhoc_lat, adhoc_lng
    else:
        anchor = pick_anchor_location(user)
        if not anchor:
            logger.info("push skipped: user %s has no location", line_user_id)
            return False
        lat, lng = anchor

    weather = await get_weather(lat, lng)
    candidates, expanded = await build_candidate_pool(
        line_user_id, lat, lng, meal_type,
        is_rainy=weather["is_rainy"], is_adhoc=is_adhoc,
    )
    if not candidates:
        _send(reply_token, line_user_id, [TextMessage(text=NO_CANDIDATES_MSG)])
        return False

    session = start_session(
        line_user_id, meal_type, lat, lng,
        weather["is_rainy"], is_adhoc, candidates,
    )
    batch = session.next_batch()
    if not batch:
        return False

    log_ids = _record_batch(
        line_user_id, batch, meal_type, weather["condition"], is_adhoc, session,
    )
    messages = list(prefix_messages or [])
    messages.extend(_build_carousel_messages(batch, log_ids, meal_type, expanded))
    _send(reply_token, line_user_id, messages)
    return True


async def push_swap_batch(line_user_id: str, reply_token: str) -> bool:
    session = get_active_session(line_user_id)
    if session is None:
        _api().reply_message(ReplyMessageRequest(
            replyToken=reply_token,
            messages=[TextMessage(text=EXHAUSTED_MSG)],
        ))
        return False

    session.batch_count += 1
    log_event(line_user_id, "swap_batch")
    batch = session.next_batch()
    expanded = False

    if not batch:
        new_candidates, _ = await build_candidate_pool(
            session.line_user_id, session.origin_lat, session.origin_lng,
            session.meal_type, is_rainy=session.is_rainy,
            is_adhoc=session.is_adhoc,
            exclude_place_ids=set(session.shown_place_ids),
            force_expanded=True,
        )
        session.extend(new_candidates)
        batch = session.next_batch()
        expanded = True

    if not batch:
        _api().reply_message(ReplyMessageRequest(
            replyToken=reply_token,
            messages=[TextMessage(text=EXHAUSTED_MSG)],
        ))
        return False

    log_ids = _record_batch(
        session.line_user_id, batch, session.meal_type,
        "", bool(session.is_adhoc), session,
    )
    messages = list(_build_carousel_messages(batch, log_ids, session.meal_type, expanded))
    if session.batch_count > GUIDANCE_BATCH_THRESHOLD and not session.guidance_sent:
        session.guidance_sent = True
        messages.append(TextMessage(text=SWAP_GUIDANCE_MSG))

    _api().reply_message(ReplyMessageRequest(
        replyToken=reply_token, messages=messages,
    ))
    return True


def push_weekly_digest_to(line_user_id: str) -> None:
    stats = weekly_stats(days=7)
    flex = flex_message_from_dict("📊 本週飲食快報", build_weekly_carousel(stats))
    _api().push_message(PushMessageRequest(to=line_user_id, messages=[flex]))


def reply_text(reply_token: str, text: str) -> None:
    _api().reply_message(ReplyMessageRequest(
        replyToken=reply_token, messages=[TextMessage(text=text)],
    ))


def reply_flex(reply_token: str, alt_text: str, contents: dict) -> None:
    _api().reply_message(ReplyMessageRequest(
        replyToken=reply_token,
        messages=[flex_message_from_dict(alt_text, contents)],
    ))
