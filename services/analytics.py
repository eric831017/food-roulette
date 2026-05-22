import json
from collections import Counter
from datetime import datetime, timedelta

from database import get_conn


def weekly_stats(days: int = 7) -> dict:
    """Aggregate stats from the past N days for the weekly digest."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    with get_conn() as conn:
        active_users = conn.execute(
            "SELECT COUNT(DISTINCT line_user_id) AS n FROM push_logs "
            "WHERE pushed_at >= ?",
            (cutoff,),
        ).fetchone()["n"]

        total_pushes = conn.execute(
            "SELECT COUNT(*) AS n FROM push_logs WHERE pushed_at >= ?",
            (cutoff,),
        ).fetchone()["n"]

        navigate_clicks = conn.execute(
            "SELECT COUNT(*) AS n FROM events "
            "WHERE event_type = 'navigate_click' AND created_at >= ?",
            (cutoff,),
        ).fetchone()["n"]

        avg_swaps_row = conn.execute(
            "SELECT AVG(swap_count) AS avg_swap FROM push_logs WHERE pushed_at >= ?",
            (cutoff,),
        ).fetchone()
        avg_swap = float(avg_swaps_row["avg_swap"] or 0.0)

        top_places = conn.execute(
            """SELECT pl.place_id, pl.place_name, pl.place_rating,
                      COUNT(*) AS clicks
               FROM events e
               JOIN push_logs pl ON pl.id = e.push_log_id
               WHERE e.event_type = 'navigate_click' AND e.created_at >= ?
               GROUP BY pl.place_id, pl.place_name
               ORDER BY clicks DESC
               LIMIT 3""",
            (cutoff,),
        ).fetchall()

        type_distribution = conn.execute(
            """SELECT place_type, COUNT(*) AS n
               FROM push_logs
               WHERE was_accepted = 1 AND pushed_at >= ?
               GROUP BY place_type
               ORDER BY n DESC""",
            (cutoff,),
        ).fetchall()

        most_blacklisted = conn.execute(
            """SELECT place_name, COUNT(DISTINCT line_user_id) AS n
               FROM user_blacklist
               WHERE created_at >= ?
               GROUP BY place_id, place_name
               ORDER BY n DESC
               LIMIT 1""",
            (cutoff,),
        ).fetchone()

        most_swappy = conn.execute(
            """SELECT line_user_id, MAX(swap_count) AS max_swaps
               FROM push_logs
               WHERE pushed_at >= ?
               GROUP BY line_user_id
               ORDER BY max_swaps DESC
               LIMIT 1""",
            (cutoff,),
        ).fetchone()

        user_quotes = conn.execute(
            """SELECT metadata FROM events
               WHERE event_type = 'user_message' AND created_at >= ?
               ORDER BY created_at DESC LIMIT 5""",
            (cutoff,),
        ).fetchall()

    quotes: list[str] = []
    for r in user_quotes:
        try:
            d = json.loads(r["metadata"] or "{}")
            text = (d.get("text") or "").strip()
            if text:
                quotes.append(text[:40])
        except Exception:
            continue

    type_total = sum(r["n"] for r in type_distribution) or 1
    type_dist = [
        (r["place_type"] or "其他", r["n"], r["n"] / type_total)
        for r in type_distribution[:5]
    ]

    ctr = (navigate_clicks / total_pushes) if total_pushes else 0.0

    return {
        "active_users": active_users,
        "total_pushes": total_pushes,
        "navigate_clicks": navigate_clicks,
        "ctr": ctr,
        "avg_swap": avg_swap,
        "top_places": [dict(r) for r in top_places],
        "type_distribution": type_dist,
        "most_swappy_user": dict(most_swappy) if most_swappy else None,
        "most_blacklisted": dict(most_blacklisted) if most_blacklisted else None,
        "user_quotes": quotes[:3],
        "start": (datetime.utcnow() - timedelta(days=days)).date().isoformat(),
        "end": datetime.utcnow().date().isoformat(),
    }


def anonymize_user(line_user_id: str) -> str:
    # Stable short code from user id
    return "U" + str(abs(hash(line_user_id)) % 9000 + 1000)
