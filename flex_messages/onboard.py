LOCATION_URI = "line://nv/location"


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
                        "uri": LOCATION_URI,
                    },
                }
            ],
        },
    }


def reset_location_card() -> dict:
    return {
        "type": "bubble",
        "size": "kilo",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                {
                    "type": "text",
                    "text": "請傳送你的新位置 📍",
                    "size": "md",
                    "color": "#444444",
                    "wrap": True,
                }
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
                        "label": "選擇位置",
                        "uri": LOCATION_URI,
                    },
                }
            ],
        },
    }
