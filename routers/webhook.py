import logging
from datetime import datetime
from urllib.parse import parse_qs

from fastapi import APIRouter, Header, HTTPException, Request
from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    FollowEvent,
    LocationMessageContent,
    MessageEvent,
    PostbackEvent,
    TextMessageContent,
    UnfollowEvent,
)
from linebot.v3.messaging import TextMessage

from config import LINE_CHANNEL_SECRET
from flex_messages.onboard import reset_location_card, welcome_card
from services.geocoding import reverse_geocode
from services.onboard import (
    add_exclusion,
    consume_pending_reset,
    ensure_user,
    get_user,
    mark_onboard_complete,
    mark_pending_reset,
    reset_user,
    set_location,
)
from services.push import (
    push_recommendation,
    push_swap_batch,
    reply_flex,
    reply_text,
)
from services.restaurant import add_blacklist, meal_type_for_hour
from services.tracking import log_event

logger = logging.getLogger(__name__)
router = APIRouter()

parser = WebhookParser(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None

ONBOARD_CONFIRMATION = "設定完成！先幫你選一家——"
RESET_TRIGGERS = {"reset", "重設", "重新設定", "重設位置"}


@router.post("/webhook")
async def line_webhook(
    request: Request, x_line_signature: str = Header(default="")
):
    body = (await request.body()).decode("utf-8")
    if parser is None:
        raise HTTPException(status_code=500, detail="LINE_CHANNEL_SECRET not set")

    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        try:
            await _dispatch(event)
        except Exception:
            logger.exception("Failed handling event")
    return {"status": "ok"}


async def _dispatch(event) -> None:
    if isinstance(event, FollowEvent):
        await _handle_follow(event)
    elif isinstance(event, UnfollowEvent):
        return
    elif isinstance(event, PostbackEvent):
        await _handle_postback(event)
    elif isinstance(event, MessageEvent):
        msg = event.message
        if isinstance(msg, LocationMessageContent):
            await _handle_location(event, msg)
        elif isinstance(msg, TextMessageContent):
            await _handle_text(event, msg)


async def _handle_follow(event: FollowEvent) -> None:
    user_id = event.source.user_id
    ensure_user(user_id)
    reply_flex(event.reply_token, "歡迎使用 Food Roulette", welcome_card())


async def _handle_location(event: MessageEvent, msg: LocationMessageContent) -> None:
    user_id = event.source.user_id
    ensure_user(user_id)
    user = get_user(user_id) or {}
    name = await reverse_geocode(msg.latitude, msg.longitude) or "未知地點"

    # Reset flow: user explicitly asked to change their saved location.
    if consume_pending_reset(user_id):
        set_location(user_id, msg.latitude, msg.longitude, name)
        if not user.get("onboard_complete"):
            mark_onboard_complete(user_id)
        reply_text(event.reply_token, f"已更新你的位置為『{name}』！")
        return

    # First-time onboard: save the location and immediately push recommendations.
    if not user.get("onboard_complete"):
        set_location(user_id, msg.latitude, msg.longitude, name)
        mark_onboard_complete(user_id)
        meal = meal_type_for_hour(datetime.now().hour)
        await push_recommendation(
            user_id, meal,
            reply_token=event.reply_token,
            prefix_messages=[TextMessage(text=ONBOARD_CONFIRMATION)],
        )
        return

    # Adhoc search: onboarded user shared a location.
    meal = meal_type_for_hour(datetime.now().hour)
    await push_recommendation(
        user_id, meal, is_adhoc=True,
        adhoc_lat=msg.latitude, adhoc_lng=msg.longitude,
        reply_token=event.reply_token,
    )


async def _handle_text(event: MessageEvent, msg: TextMessageContent) -> None:
    user_id = event.source.user_id
    ensure_user(user_id)
    text = (msg.text or "").strip()
    lower = text.lower()

    if lower in RESET_TRIGGERS:
        _prompt_reset(user_id, event.reply_token)
        return

    if text.startswith("不要推") and len(text) > 3:
        excluded = text[3:].strip()
        if excluded:
            add_exclusion(user_id, excluded)
            reply_text(event.reply_token, f"好的，之後不會推「{excluded}」類型給你。")
            return

    log_event(user_id, "user_message", metadata={"text": text})
    reply_text(event.reply_token, "收到你的回饋！")


async def _handle_postback(event: PostbackEvent) -> None:
    user_id = event.source.user_id
    data = event.postback.data or ""
    params = {k: v[0] for k, v in parse_qs(data).items()}
    action = params.get("action")

    if action == "swap_batch":
        await push_swap_batch(user_id, event.reply_token)
        return

    if action == "reset_location":
        _prompt_reset(user_id, event.reply_token)
        return

    if action == "blacklist":
        place_id = params.get("place_id", "")
        place_name = params.get("place_name", "")
        if not place_id:
            return
        add_blacklist(user_id, place_id, place_name)
        log_event(
            user_id, "blacklist",
            push_log_id=int(params.get("push_log_id") or 0) or None,
            metadata={"place_id": place_id, "place_name": place_name},
        )
        reply_text(event.reply_token, f"好的，以後不會再推薦 {place_name} 了。")
        return


def _prompt_reset(user_id: str, reply_token: str) -> None:
    mark_pending_reset(user_id)
    reply_flex(reply_token, "請傳送你的新位置 📍", reset_location_card())
