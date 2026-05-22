import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Taipei")

DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/food_roulette.db")
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# Tracking-ID secret (for signing redirect tracking IDs)
TRACKING_SECRET = os.getenv("TRACKING_SECRET", "food-roulette-poc-secret")

# Recommendation tuning
DEFAULT_RADIUS_M = 1500
RAINY_RADIUS_M = 800
EXPANDED_RADIUS_M = 3000
MIN_POOL_SIZE = 5
MIN_RATING = 3.5
DEDUP_DAYS = 3
