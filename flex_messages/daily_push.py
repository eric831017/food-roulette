from config import GOOGLE_MAPS_API_KEY
from models import Restaurant
from services.tracking import navigate_url_for

MEAL_LABELS = {
    "breakfast": "☀️ 早安，今天吃這個",
    "lunch": "🌞 午餐時間到",
    "dinner": "🌙 晚餐吃什麼",
}

PLACEHOLDER_PHOTO = (
    "https://via.placeholder.com/800x520.png?text=Food+Roulette"
)


def _photo_url(photo_reference: str | None) -> str:
    if not photo_reference or not GOOGLE_MAPS_API_KEY:
        return PLACEHOLDER_PHOTO
    return (
        "https://maps.googleapis.com/maps/api/place/photo"
        f"?maxwidth=800&photo_reference={photo_reference}&key={GOOGLE_MAPS_API_KEY}"
    )


def _format_distance(m: int) -> str:
    if m < 1000:
        return f"{m}m"
    return f"{m / 1000:.1f}km"


def _price_label(level: int | None) -> str:
    if level is None:
        return ""
    if level <= 1:
        return "$"
    if level == 2:
        return "$$"
    return "$$$"


def build_daily_push(restaurant: Restaurant, push_log_id: int, meal_type: str) -> dict:
    contents = [
        {
            "type": "text",
            "text": restaurant.name or "（未命名餐廳）",
            "weight": "bold",
            "size": "lg",
            "wrap": True,
        }
    ]

    meta_box_contents: list[dict] = [
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "xs",
            "contents": [
                {"type": "text", "text": "★", "size": "sm", "color": "#EF9F27", "flex": 0},
                {
                    "type": "text",
                    "text": f"{restaurant.rating:.1f}",
                    "size": "sm",
                    "color": "#888888",
                    "flex": 0,
                },
            ],
        },
        {
            "type": "text",
            "text": f"🚶 {_format_distance(restaurant.distance_meters)}",
            "size": "sm",
            "color": "#888888",
            "flex": 0,
        },
    ]
    price = _price_label(restaurant.price_level)
    if price:
        meta_box_contents.append(
            {"type": "text", "text": price, "size": "sm", "color": "#888888", "flex": 0}
        )

    contents.append(
        {
            "type": "box",
            "layout": "horizontal",
            "spacing": "md",
            "contents": meta_box_contents,
        }
    )

    contents.append(
        {
            "type": "text",
            "text": MEAL_LABELS.get(meal_type, ""),
            "size": "xs",
            "color": "#AAAAAA",
            "margin": "md",
        }
    )

    return {
        "type": "bubble",
        "size": "mega",
        "hero": {
            "type": "image",
            "url": _photo_url(restaurant.photo_reference),
            "size": "full",
            "aspectRatio": "20:13",
            "aspectMode": "cover",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": contents,
        },
        "footer": {
            "type": "box",
            "layout": "horizontal",
            "spacing": "none",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "帶我去",
                        "uri": navigate_url_for(push_log_id),
                    },
                    "style": "primary",
                    "color": "#0F6E56",
                    "height": "sm",
                    "flex": 1,
                },
                {
                    "type": "button",
                    "action": {
                        "type": "postback",
                        "label": "換一個",
                        "data": f"action=swap&push_log_id={push_log_id}",
                    },
                    "style": "secondary",
                    "height": "sm",
                    "flex": 1,
                },
            ],
        },
    }


def build_alt_text(restaurant: Restaurant, meal_type: str) -> str:
    return f"{MEAL_LABELS.get(meal_type, '推薦')}：{restaurant.name}"
