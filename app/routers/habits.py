from __future__ import annotations

from typing import List
from datetime import datetime, date as Date

from fastapi import APIRouter, HTTPException, Query, status

from app.db import mongodb
from app.models import Habit, HabitCreate, HabitUpdate
from app.utils import get_default_user_id, now_utc, to_object_id

from app.auth_utils import get_current_user_id
from fastapi import Depends

router = APIRouter()


@router.post("", response_model=Habit)
async def create_habit(payload: HabitCreate,
    user_id: str = Depends(get_current_user_id)):
        
    doc = payload.model_dump()
    
    # convert date to datetime for MongoDB compatibility
    if doc.get("startDate") and isinstance(doc["startDate"], Date):
        doc["startDate"] = datetime.combine(doc["startDate"], datetime.min.time())
    
    doc.update({"userId": user_id, "isActive": True, "createdAt": now_utc(), "updatedAt": now_utc()})
    res = await mongodb.collection("habits").insert_one(doc)
    created = await mongodb.collection("habits").find_one({"_id": res.inserted_id})
    return Habit(**created)


@router.get("", response_model=List[Habit])
async def list_habits(active_only: bool = Query(default=False),
    user_id: str = Depends(get_current_user_id)):
        
    q = {"userId": user_id}
    if active_only:
        q["isActive"] = True

    docs = await mongodb.collection("habits").find(q).sort("createdAt", -1).to_list(length=500)
    return [Habit(**d) for d in docs]


@router.get("/{habit_id}", response_model=Habit)
async def get_habit(habit_id: str,
    user_id: str = Depends(get_current_user_id)):

    oid = to_object_id(habit_id)
    doc = await mongodb.collection("habits").find_one({"_id": oid, "userId": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return Habit(**doc)


@router.patch("/{habit_id}", response_model=Habit)
async def update_habit(habit_id: str, payload: HabitUpdate,
    user_id: str = Depends(get_current_user_id)):

    oid = to_object_id(habit_id)

    update = payload.model_dump(exclude_unset=True)
    
    # convert date to datetime for MongoDB compatibility
    if "startDate" in update and isinstance(update["startDate"], Date):
        update["startDate"] = datetime.combine(update["startDate"], datetime.min.time())
        
    update["updatedAt"] = now_utc()

    res = await mongodb.collection("habits").update_one(
        {"_id": oid, "userId": user_id},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")

    doc = await mongodb.collection("habits").find_one({"_id": oid, "userId": user_id})
    return Habit(**doc)


@router.delete("/{habit_id}")
async def delete_habit(habit_id: str,
    user_id: str = Depends(get_current_user_id)):

    oid = to_object_id(habit_id)
    res = await mongodb.collection("habits").delete_one({"_id": oid, "userId": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return {"deleted": True}