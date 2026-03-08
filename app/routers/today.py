from __future__ import annotations

from datetime import datetime, date as Date
from typing import Any, Dict

from fastapi import APIRouter, Query

from app.db import mongodb
from app.utils import get_default_user_id, weekday_sun0

router = APIRouter()


def habit_expected_today(habit_doc: Dict[str, Any], day: Date) -> bool:
    if not habit_doc.get("isActive", True):
        return False

    start_date = habit_doc.get("startDate")
    if start_date and day < start_date:
        return False

    sched = habit_doc.get("schedule", {}) or {}
    stype = sched.get("type", "daily")

    if stype == "daily":
        return True

    if stype == "weekdays":
        wd = weekday_sun0(day)
        return wd in (1, 2, 3, 4, 5)

    if stype == "custom":
        days = sched.get("daysOfWeek") or []
        wd = weekday_sun0(day)
        return wd in days

    if stype == "weekly_x":
        # MVP: treat as expected; quota logic can be added later
        return True

    return True


@router.get("")
async def today_view(date: str = Query(default=None)):
    user_id = get_default_user_id()

    if date:
        y, m, d = map(int, date.split("-"))
        day = Date(y, m, d)
    else:
        day = Date.today()

    # convert date to datetime for MongoDB query
    day_dt = datetime.combine(day, datetime.min.time())
    
    tasks = await mongodb.collection("tasks").find(
        {"userId": user_id, "scheduledDate": day_dt}
    ).sort("createdAt", -1).to_list(length=500)

    habits = await mongodb.collection("habits").find(
        {"userId": user_id, "isActive": True}
    ).sort("createdAt", -1).to_list(length=500)

    expected = [h for h in habits if habit_expected_today(h, day)]
    habit_ids = [h["_id"] for h in expected]

    logs = []
    if habit_ids:
        logs = await mongodb.collection("habitLogs").find(
            {"userId": user_id, "habitId": {"$in": habit_ids}, "date": day_dt}
        ).to_list(length=1000)

    log_by_habit = {l["habitId"]: l for l in logs}

    # normalize ids for frontend friendliness
    for t in tasks:
        t["_id"] = str(t["_id"])

    habits_out = []
    for h in expected:
        h_id = h["_id"]
        log = log_by_habit.get(h_id)
        habits_out.append(
            {
                "habit": {"_id": str(h_id), "name": h.get("name"), "schedule": h.get("schedule")},
                "statusToday": (log.get("status") if log else "none"),
                "logId": (str(log["_id"]) if log else None),
            }
        )

    return {"date": day.isoformat(), "tasks": tasks, "habits": habits_out}