# Food Roulette

A LINE Official Account bot POC that kills decision fatigue: every day at
06:30 / 11:30 / 17:30, push one weighted-random restaurant. The user either
taps **帶我去** (navigate) or **換一個** (re-roll).

## Stack

- Python 3.11, FastAPI, APScheduler, SQLite
- `line-bot-sdk` v3 (Messaging API)
- Google Places API (Nearby Search + Photos + Details)
- OpenWeatherMap (weather-aware radius)

## Project layout

```
food-roulette/
├── main.py
├── config.py
├── database.py
├── models.py
├── scheduler.py
├── routers/
│   ├── webhook.py
│   └── redirect.py
├── services/
│   ├── restaurant.py
│   ├── weather.py
│   ├── push.py
│   ├── onboard.py
│   ├── analytics.py
│   ├── geocoding.py
│   └── tracking.py
└── flex_messages/
    ├── daily_push.py
    ├── weekly_digest.py
    └── onboard.py
```

## Local run

```bash
cp .env.example .env   # fill in tokens
pip install -r requirements.txt --break-system-packages
uvicorn main:app --host 0.0.0.0 --port 8000
```

LINE webhook URL: `https://<your-domain>/webhook`.
Redirect tracker: `https://<your-domain>/r/{tracking_id}`.

## VPS deploy sketch

```bash
ssh <user>@<host>
cd ~ && git clone <repo> food-roulette && cd food-roulette
cp .env.example .env && vim .env
pip install -r requirements.txt --break-system-packages
```

systemd unit `/etc/systemd/system/food-roulette.service`:

```ini
[Unit]
Description=Food Roulette LINE bot
After=network.target

[Service]
User=<user>
WorkingDirectory=/home/<user>/food-roulette
EnvironmentFile=/home/<user>/food-roulette/.env
ExecStart=/usr/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Front with Caddy for HTTPS:

```
yourdomain.tld {
    reverse_proxy 127.0.0.1:8000
}
```

`TIMEZONE=Asia/Taipei` in `.env`; APScheduler uses that tz directly so
you do not need to convert from UTC.

## Phase status

1. Skeleton (FastAPI + webhook + SQLite + onboard) — done
2. Recommendation (Places + weighted random + Flex push) — done
3. Interactions (swap postback + redirect tracker + adhoc) — done
4. Intelligence (weather + meal-type weights + preference learning + dedup) — done
5. Weekly digest (stats + carousel Flex) — done
6. Deploy (VPS + HTTPS + systemd) — manual step
