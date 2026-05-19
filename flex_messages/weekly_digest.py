from services.analytics import anonymize_user


def _bar(label: str, pct: float) -> dict:
    filled = max(1, int(round(pct * 10)))
    bar = "█" * filled + "░" * (10 - filled)
    return {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            {"type": "text", "text": label, "size": "sm", "color": "#444444", "flex": 3},
            {"type": "text", "text": bar, "size": "sm", "color": "#0F6E56", "flex": 5, "align": "start"},
            {
                "type": "text",
                "text": f"{int(pct * 100)}%",
                "size": "sm",
                "color": "#888888",
                "flex": 2,
                "align": "end",
            },
        ],
    }


def build_weekly_carousel(stats: dict) -> dict:
    bubbles = [_top_places_card(stats), _social_card(stats)]
    return {"type": "carousel", "contents": bubbles}


def _top_places_card(stats: dict) -> dict:
    header = {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
            {"type": "text", "text": "📊 本週飲食快報", "weight": "bold", "size": "lg"},
            {
                "type": "text",
                "text": f"{stats['start']} ~ {stats['end']}  ·  {stats['active_users']} 人活躍",
                "size": "xs",
                "color": "#888888",
            },
        ],
    }

    body_contents: list[dict] = [
        {"type": "text", "text": "🏆 本週人氣餐廳", "weight": "bold", "size": "md"}
    ]

    if stats["top_places"]:
        for p in stats["top_places"]:
            body_contents.append(
                {
                    "type": "box",
                    "layout": "horizontal",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": p["place_name"],
                            "size": "sm",
                            "color": "#444444",
                            "flex": 5,
                            "wrap": True,
                        },
                        {
                            "type": "text",
                            "text": f"{p['clicks']} 人前往",
                            "size": "xs",
                            "color": "#888888",
                            "flex": 3,
                            "align": "end",
                        },
                    ],
                }
            )
    else:
        body_contents.append(
            {"type": "text", "text": "本週還沒有人按「帶我去」", "size": "sm", "color": "#888888"}
        )

    body_contents.append({"type": "separator", "margin": "md"})
    body_contents.append({"type": "text", "text": "🍽 料理分布", "weight": "bold", "size": "md", "margin": "md"})

    if stats["type_distribution"]:
        for label, _n, pct in stats["type_distribution"]:
            body_contents.append(_bar(label, pct))
    else:
        body_contents.append(
            {"type": "text", "text": "尚無資料", "size": "sm", "color": "#888888"}
        )

    return {
        "type": "bubble",
        "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [header]},
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
    }


def _social_card(stats: dict) -> dict:
    body_contents: list[dict] = [
        {"type": "text", "text": "🎲 本週最猶豫", "weight": "bold", "size": "md"}
    ]

    if stats["most_swappy_user"] and stats["most_swappy_user"]["max_swaps"]:
        code = anonymize_user(stats["most_swappy_user"]["line_user_id"])
        body_contents.append(
            {
                "type": "text",
                "text": f"{code} 連按了 {stats['most_swappy_user']['max_swaps']} 次「換一個」才出門。",
                "size": "sm",
                "color": "#444444",
                "wrap": True,
            }
        )
    else:
        body_contents.append(
            {"type": "text", "text": "大家都很果斷！", "size": "sm", "color": "#888888"}
        )

    body_contents.append({"type": "separator", "margin": "md"})
    body_contents.append(
        {"type": "text", "text": "💬 大家怎麼說", "weight": "bold", "size": "md", "margin": "md"}
    )

    if stats["user_quotes"]:
        for q in stats["user_quotes"]:
            body_contents.append(
                {
                    "type": "text",
                    "text": f"「{q}」",
                    "size": "sm",
                    "color": "#444444",
                    "wrap": True,
                }
            )
    else:
        body_contents.append(
            {"type": "text", "text": "（本週沒有人留言）", "size": "sm", "color": "#888888"}
        )

    body_contents.append({"type": "separator", "margin": "md"})
    body_contents.append(
        {
            "type": "box",
            "layout": "horizontal",
            "margin": "md",
            "contents": [
                _stat_block("推薦", str(stats["total_pushes"])),
                _stat_block("點擊率", f"{int(stats['ctr'] * 100)}%"),
                _stat_block("平均換", f"{stats['avg_swap']:.1f}"),
            ],
        }
    )

    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": body_contents,
        },
    }


def _stat_block(label: str, value: str) -> dict:
    return {
        "type": "box",
        "layout": "vertical",
        "flex": 1,
        "contents": [
            {"type": "text", "text": value, "weight": "bold", "size": "lg", "align": "center", "color": "#0F6E56"},
            {"type": "text", "text": label, "size": "xs", "align": "center", "color": "#888888"},
        ],
    }
