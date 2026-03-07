from __future__ import annotations

from datetime import datetime, timedelta, date as Date
from fastapi import APIRouter, Query

from app.db import mongodb
from app.utils import get_default_user_id, to_object_id, weekday_sun0

router = APIRouter()


def habit_expected_on_day(habit: dict, day: Date) -> bool:
    if not habit.get("isActive", True):
        return False

    start_date = habit.get("startDate")
    if start_date and day < start_date:
        return False

    sched = habit.get("schedule", {}) or {}
    stype = sched.get("type", "daily")

    if stype == "daily":
        return True
    if stype == "weekdays":
        return weekday_sun0(day) in (1, 2, 3, 4, 5)
    if stype == "custom":
        return weekday_sun0(day) in (sched.get("daysOfWeek") or [])
    if stype == "weekly_x":
        return True  # MVP
    return True


@router.get("/tasks/completion-rate")
async def task_completion_rate(days: int = Query(default=7, ge=1, le=365)):
    """
    Simple completion rate over last N days:
      completed tasks / created tasks
    """
    user_id = get_default_user_id()

    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=days)

    created = await mongodb.collection("tasks").count_documents(
        {"userId": user_id, "createdAt": {"$gte": start_dt}}
    )
    completed = await mongodb.collection("tasks").count_documents(
        {"userId": user_id, "status": "done", "completedAt": {"$gte": start_dt}}
    )

    return {
        "windowDays": days,
        "created": created,
        "completed": completed,
        "completionRate": (completed / created) if created else None,
    }


@router.get("/habits/streak")
async def habit_streak(habit_id: str):
    """
    Current streak: consecutive expected days ending today where log status == done.
    """
    user_id = get_default_user_id()
    hid = to_object_id(habit_id)

    habit = await mongodb.collection("habits").find_one({"_id": hid, "userId": user_id})
    if not habit:
        return {"habitId": habit_id, "streak": 0}

    today = Date.today()
    streak = 0

    # Look back up to 365 days for MVP
    for i in range(0, 365):
        day = today - timedelta(days=i)

        if not habit_expected_on_day(habit, day):
            continue  # don't break on non-expected days

        log = await mongodb.collection("habitLogs").find_one(
            {"userId": user_id, "habitId": hid, "date": day}
        )
        if log and log.get("status") == "done":
            streak += 1
        else:
            break

    return {"habitId": habit_id, "streak": streak}