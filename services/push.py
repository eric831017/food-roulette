import logging
from typing import Optional

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    FlexMessage,
    FlexContainer,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from config import LINE_CHANNEL_ACCESS_TOKEN
from flex_messages.daily_push import build_alt_text, build_daily_push
from flex_messages.weekly_digest import build_weekly_carousel
from services.analytics import weekly_stats
from services.onboard import get_user, pick_anchor_location
from services.restaurant import (
    build_candidate_pool,
    navigation_count_7d,
    record_push,
)
from services.session import (
    GUIDANCE_SWAP_THRESHOLD,
    bind_log,
    get_session_for_log,
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


def _api() -> MessagingApi:
    cfg = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    return MessagingApi(ApiClient(cfg))


def flex_message_from_dict(alt_text: str, contents: dict) -> FlexMessage:
    return FlexMessage(altText=alt_text, contents=FlexContainer.from_dict(contents))


def _card_for(restaurant, push_log_id: int, meal_type: str, expanded: bool) -> FlexMessage:
    social_count = navigation_count_7d(restaurant.place_id)
    return flex_message_from_dict(
        build_alt_text(restaurant, meal_type),
        build_daily_push(
            restaurant, push_log_id, meal_type,
            expanded=expanded, social_count=social_count,
        ),
    )


async def push_recommendation(
    line_user_id: str, meal_type: str, is_adhoc: bool = False,
    adhoc_lat: Optional[float] = None, adhoc_lng: Optional[float] = None,
    reply_token: Optional[str] = None,
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
        from datetime import datetime
        anchor = pick_anchor_location(user, datetime.now().isoweekday())
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
        if reply_token:
            _api().reply_message(ReplyMessageRequest(
                replyToken=reply_token,
                messages=[TextMessage(text="這附近找不到合適的餐廳，再試試其他地點吧。")],
            ))
        return False

    session = start_session(
        line_user_id, meal_type, lat, lng,
        weather["is_rainy"], is_adhoc, candidates,
    )
    restaurant = session.next_restaurant()
    if not restaurant:
        return False

    push_log_id = record_push(
        line_user_id, restaurant, meal_type, weather["condition"], is_adhoc
    )
    bind_log(push_log_id, session)
    flex = _card_for(restaurant, push_log_id, meal_type, expanded)

    if reply_token:
        _api().reply_message(ReplyMessageRequest(replyToken=reply_token, messages=[flex]))
    else:
        _api().push_message(PushMessageRequest(to=line_user_id, messages=[flex]))
    return True


async def push_swap(line_user_id: str, original_push_log_id: int, reply_token: str) -> bool:
    from services.restaurant import get_push_log, increment_swap

    original = get_push_log(original_push_log_id)
    if not original:
        return False

    meal_type = original["meal_type"]
    increment_swap(original_push_log_id)
    log_event(line_user_id, "swap", push_log_id=original_push_log_id)

    session = get_session_for_log(original_push_log_id)
    if session is None:
        session = await _rebuild_session(line_user_id, original)
        if session is None:
            _api().reply_message(ReplyMessageRequest(
                replyToken=reply_token,
                messages=[TextMessage(text=EXHAUSTED_MSG)],
            ))
            return False

    session.swap_count += 1
    restaurant = session.next_restaurant()
    expanded = False

    if restaurant is None:
        # Cache exhausted: widen the radius and exclude everything seen so far.
        new_candidates, _ = await build_candidate_pool(
            session.line_user_id, session.origin_lat, session.origin_lng,
            session.meal_type, is_rainy=session.is_rainy,
            is_adhoc=session.is_adhoc,
            exclude_place_ids=set(session.shown_place_ids),
            force_expanded=True,
        )
        session.extend(new_candidates)
        restaurant = session.next_restaurant()
        expanded = True

    if restaurant is None:
        _api().reply_message(ReplyMessageRequest(
            replyToken=reply_token,
            messages=[TextMessage(text=EXHAUSTED_MSG)],
        ))
        return False

    new_log_id = record_push(
        session.line_user_id, restaurant, meal_type,
        original["weather_condition"] or "", bool(session.is_adhoc),
    )
    bind_log(new_log_id, session)
    flex = _card_for(restaurant, new_log_id, meal_type, expanded)

    messages = [flex]
    if session.swap_count > GUIDANCE_SWAP_THRESHOLD and not session.guidance_sent:
        session.guidance_sent = True
        messages.append(TextMessage(text=SWAP_GUIDANCE_MSG))

    _api().reply_message(ReplyMessageRequest(replyToken=reply_token, messages=messages))
    return True


async def _rebuild_session(line_user_id: str, original):
    """Reconstruct a session after a restart, using the expanded radius."""
    user = get_user(line_user_id)
    is_adhoc = bool(original["is_adhoc"])
    if is_adhoc:
        lat, lng = original["place_lat"], original["place_lng"]
    else:
        if not user:
            return None
        from datetime import datetime
        anchor = pick_anchor_location(user, datetime.now().isoweekday())
        if not anchor:
            return None
        lat, lng = anchor

    weather = await get_weather(lat, lng)
    candidates, _ = await build_candidate_pool(
        line_user_id, lat, lng, original["meal_type"],
        is_rainy=weather["is_rainy"], is_adhoc=is_adhoc,
        exclude_place_ids={original["place_id"]},
    )
    if not candidates:
        return None
    return start_session(
        line_user_id, original["meal_type"], lat, lng,
        weather["is_rainy"], is_adhoc, candidates,
    )


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
