import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import init_db
from routers import redirect, webhook
from scheduler import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    scheduler = start_scheduler()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Food Roulette", lifespan=lifespan)
app.include_router(webhook.router)
app.include_router(redirect.router)


@app.get("/")
def health():
    return {"status": "ok", "service": "food-roulette"}
