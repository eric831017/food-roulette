def welcome_card() -> dict:
    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "Food Roulette",
                    "weight": "bold",
                    "size": "xl",
                    "color": "#0F6E56",
                },
                {
                    "type": "text",
                    "text": "每天幫你決定吃什麼，不用再想。",
                    "size": "md",
                    "color": "#444444",
                    "wrap": True,
                    "margin": "sm",
                },
                {
                    "type": "text",
                    "text": "先告訴我你常待的地方，每天 06:30 / 11:30 / 17:30 我會直接推薦一家。",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#0F6E56",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "設定我的位置",
                        "uri": "https://line.me/R/nv/location",
                    },
                }
            ],
        },
    }


def ask_second_location_card(first_name: str) -> dict:
    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "收到！",
                    "weight": "bold",
                    "size": "lg",
                },
                {
                    "type": "text",
                    "text": f"已設為你的位置「{first_name}」。",
                    "size": "sm",
                    "color": "#444444",
                    "wrap": True,
                },
                {
                    "type": "text",
                    "text": "還有第二個常去的地方嗎？（例如：週末家裡）",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#0F6E56",
                    "height": "sm",
                    "action": {
                        "type": "uri",
                        "label": "再設一個",
                        "uri": "https://line.me/R/nv/location",
                    },
                },
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "postback",
                        "label": "這樣就好",
                        "data": "action=onboard_complete",
                    },
                },
            ],
        },
    }


def onboard_summary_card(loc1_name: str, loc2_name: str | None) -> dict:
    rows = [
        {
            "type": "box",
            "layout": "baseline",
            "spacing": "sm",
            "contents": [
                {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                {"type": "text", "text": loc1_name or "—", "size": "sm", "color": "#444444"},
            ],
        }
    ]
    if loc2_name:
        rows.append(
            {
                "type": "box",
                "layout": "baseline",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": "📍", "size": "sm", "flex": 0},
                    {"type": "text", "text": loc2_name, "size": "sm", "color": "#444444"},
                ],
            }
        )

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {"type": "text", "text": "設定完成 ✓", "weight": "bold", "size": "lg"},
                *rows,
                {
                    "type": "text",
                    "text": "明天早上 06:30 開始，我會幫你決定早餐。隨時傳位置給我，也能馬上推薦！",
                    "size": "sm",
                    "color": "#888888",
                    "wrap": True,
                    "margin": "md",
                },
            ],
        },
    }
