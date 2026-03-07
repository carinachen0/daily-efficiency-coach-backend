from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from app.db import connect_to_mongo, close_mongo_connection
from app.routers.tasks import router as tasks_router
from app.routers.habits import router as habits_router
from app.routers.habit_logs import router as habit_logs_router
from app.routers.today import router as today_router
from app.routers.analytics import router as analytics_router

load_dotenv()

app = FastAPI(title="Daily Efficiency Coach API", version="0.1.0")


@app.on_event("startup")
async def startup():
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown():
    await close_mongo_connection()


@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(tasks_router, prefix="/tasks", tags=["tasks"])
app.include_router(habits_router, prefix="/habits", tags=["habits"])
app.include_router(habit_logs_router, prefix="/habit-logs", tags=["habit-logs"])
app.include_router(today_router, prefix="/today", tags=["today"])
app.include_router(analytics_router, prefix="/analytics", tags=["analytics"])