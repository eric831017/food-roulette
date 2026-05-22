import logging
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

from config import LINE_CHANNEL_SECRET
from flex_messages.onboard import (
    ask_second_location_card,
    onboard_summary_card,
    welcome_card,
)
from services.geocoding import reverse_geocode
from services.onboard import (
    add_exclusion,
    ensure_user,
    get_user,
    mark_onboard_complete,
    next_empty_slot,
    reset_user,
    set_location,
)
from services.push import (
    push_recommendation,
    push_swap,
    reply_flex,
    reply_text,
)
from services.restaurant import add_blacklist, get_push_log, mark_accepted
from services.tracking import log_event

logger = logging.getLogger(__name__)
router = APIRouter()

parser = WebhookParser(LINE_CHANNEL_SECRET) if LINE_CHANNEL_SECRET else None


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
        # Soft-keep data; nothing to do for POC.
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

    # Onboard: still has empty slots and not yet marked complete.
    slot = next_empty_slot(user)
    if not user.get("onboard_complete") and slot is not None:
        name = await reverse_geocode(msg.latitude, msg.longitude) or "未知地點"
        set_location(user_id, slot, msg.latitude, msg.longitude, name)
        if slot == 1:
            reply_flex(
                event.reply_token,
                f"已設定位置：{name}",
                ask_second_location_card(name),
            )
        else:
            user = get_user(user_id) or {}
            mark_onboard_complete(user_id)
            reply_flex(
                event.reply_token,
                "設定完成",
                onboard_summary_card(user["location_1_name"], user.get("location_2_name")),
            )
        return

    # Adhoc search: user is onboarded and shared a location.
    from datetime import datetime
    hour = datetime.now().hour
    meal = "breakfast" if hour < 10 else ("lunch" if hour < 15 else "dinner")
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

    if lower in {"reset", "重設", "重新設定"}:
        reset_user(user_id)
        reply_flex(event.reply_token, "重新開始", welcome_card())
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

    if action == "onboard_complete":
        mark_onboard_complete(user_id)
        user = get_user(user_id) or {}
        reply_flex(
            event.reply_token,
            "設定完成",
            onboard_summary_card(
                user.get("location_1_name") or "—", user.get("location_2_name")
            ),
        )
        return

    if action == "swap":
        try:
            push_log_id = int(params.get("push_log_id", "0"))
        except ValueError:
            return
        await push_swap(user_id, push_log_id, event.reply_token)
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
