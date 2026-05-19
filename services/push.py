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
from models import Restaurant
from services.analytics import weekly_stats
from services.onboard import get_user, pick_anchor_location
from services.restaurant import pick_restaurant, record_push
from services.tracking import log_event
from services.weather import get_weather

logger = logging.getLogger(__name__)


def _api() -> MessagingApi:
    cfg = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
    return MessagingApi(ApiClient(cfg))


def flex_message_from_dict(alt_text: str, contents: dict) -> FlexMessage:
    return FlexMessage(altText=alt_text, contents=FlexContainer.from_dict(contents))


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
    restaurant = await pick_restaurant(
        line_user_id, lat, lng, meal_type,
        is_rainy=weather["is_rainy"], is_adhoc=is_adhoc,
    )
    if not restaurant:
        if reply_token:
            _api().reply_message(ReplyMessageRequest(
                replyToken=reply_token,
                messages=[TextMessage(text="這附近找不到合適的餐廳，再試試其他地點吧。")],
            ))
        return False

    push_log_id = record_push(
        line_user_id, restaurant, meal_type, weather["condition"], is_adhoc
    )
    flex = flex_message_from_dict(
        build_alt_text(restaurant, meal_type),
        build_daily_push(restaurant, push_log_id, meal_type),
    )

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

    user = get_user(line_user_id)
    if not user:
        return False

    from datetime import datetime
    if original["is_adhoc"]:
        lat, lng = original["place_lat"], original["place_lng"]  # rough fallback origin
        # we no longer have original origin; use stored place as proxy
    else:
        anchor = pick_anchor_location(user, datetime.now().isoweekday())
        if not anchor:
            return False
        lat, lng = anchor

    weather = await get_weather(lat, lng)
    excluded = {original["place_id"]}
    restaurant = await pick_restaurant(
        line_user_id, lat, lng, meal_type,
        is_rainy=weather["is_rainy"],
        exclude_place_ids=excluded,
        is_adhoc=bool(original["is_adhoc"]),
    )
    if not restaurant:
        _api().reply_message(ReplyMessageRequest(
            replyToken=reply_token,
            messages=[TextMessage(text="附近真的沒得換了😅 換個地點再試試？")],
        ))
        return False

    new_log_id = record_push(
        line_user_id, restaurant, meal_type,
        weather["condition"], bool(original["is_adhoc"]),
    )
    flex = flex_message_from_dict(
        build_alt_text(restaurant, meal_type),
        build_daily_push(restaurant, new_log_id, meal_type),
    )
    _api().reply_message(ReplyMessageRequest(replyToken=reply_token, messages=[flex]))
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
