from __future__ import annotations

from typing import List, Optional
from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query

from app.db import mongodb
from app.models import HabitLog, HabitLogCreate, HabitLogUpdate
from app.utils import get_default_user_id, now_utc, to_object_id

router = APIRouter()


@router.post("", response_model=HabitLog)
async def upsert_log(payload: HabitLogCreate):
    """
    One log per (habitId, date). Upsert = create if missing, otherwise update.
    """
    user_id = get_default_user_id()
    habit_oid = to_object_id(payload.habitId)
    day = payload.date

    update = payload.model_dump()
    update["habitId"] = habit_oid
    update["userId"] = user_id
    update["updatedAt"] = now_utc()

    if update.get("status") == "done" and update.get("completedAt") is None:
        update["completedAt"] = now_utc()

    await mongodb.collection("habitLogs").update_one(
        {"userId": user_id, "habitId": habit_oid, "date": day},
        {
            "$set": {
                "status": update["status"],
                "value": update.get("value"),
                "startedAt": update.get("startedAt"),
                "completedAt": update.get("completedAt"),
                "timeSpentSec": update.get("timeSpentSec"),
                "note": update.get("note"),
                "updatedAt": update["updatedAt"],
            },
            "$setOnInsert": {
                "userId": user_id,
                "habitId": habit_oid,
                "date": day,
                "createdAt": now_utc(),
            },
        },
        upsert=True,
    )

    saved = await mongodb.collection("habitLogs").find_one(
        {"userId": user_id, "habitId": habit_oid, "date": day}
    )
    if not saved:
        raise HTTPException(status_code=500, detail="Failed to save habit log")

    return HabitLog(**saved)


@router.get("", response_model=List[HabitLog])
async def list_logs(
    habit_id: Optional[str] = Query(default=None),
    start: Optional[str] = Query(default=None),
    end: Optional[str] = Query(default=None),
):
    user_id = get_default_user_id()
    q = {"userId": user_id}

    if habit_id:
        q["habitId"] = to_object_id(habit_id)

    if start or end:
        q["date"] = {}
        if start:
            y, m, d = map(int, start.split("-"))
            q["date"]["$gte"] = Date(y, m, d)
        if end:
            y, m, d = map(int, end.split("-"))
            q["date"]["$lte"] = Date(y, m, d)

    docs = await mongodb.collection("habitLogs").find(q).sort("date", -1).to_list(length=1000)
    return [HabitLog(**d) for d in docs]


@router.patch("/{log_id}", response_model=HabitLog)
async def update_log(log_id: str, payload: HabitLogUpdate):
    user_id = get_default_user_id()
    oid = to_object_id(log_id)

    update = payload.model_dump(exclude_unset=True)
    update["updatedAt"] = now_utc()

    if update.get("status") == "done" and "completedAt" not in update:
        update["completedAt"] = now_utc()

    res = await mongodb.collection("habitLogs").update_one(
        {"_id": oid, "userId": user_id},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Habit log not found")

    doc = await mongodb.collection("habitLogs").find_one({"_id": oid, "userId": user_id})
    return HabitLog(**doc)


@router.delete("/{log_id}")
async def delete_log(log_id: str):
    user_id = get_default_user_id()
    oid = to_object_id(log_id)
    res = await mongodb.collection("habitLogs").delete_one({"_id": oid, "userId": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habit log not found")
    return {"deleted": True}