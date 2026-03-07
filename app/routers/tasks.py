from __future__ import annotations

from typing import List, Optional
from datetime import date as Date

from fastapi import APIRouter, HTTPException, Query, status

from app.db import mongodb
from app.models import Task, TaskCreate, TaskUpdate
from app.utils import get_default_user_id, now_utc, to_object_id

router = APIRouter()


@router.post("", response_model=Task)
async def create_task(payload: TaskCreate):
    user_id = get_default_user_id()
    doc = payload.model_dump()
    doc.update(
        {"userId": user_id, "status": "todo", "createdAt": now_utc(), "updatedAt": now_utc()}
    )
    res = await mongodb.collection("tasks").insert_one(doc)
    created = await mongodb.collection("tasks").find_one({"_id": res.inserted_id})
    return Task(**created)


@router.get("", response_model=List[Task])
async def list_tasks(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    scheduled_date: Optional[str] = Query(default=None),
):
    user_id = get_default_user_id()
    q = {"userId": user_id}

    if status_filter:
        q["status"] = status_filter

    if scheduled_date:
        y, m, d = map(int, scheduled_date.split("-"))
        q["scheduledDate"] = Date(y, m, d)

    docs = await mongodb.collection("tasks").find(q).sort("createdAt", -1).to_list(length=500)
    return [Task(**d) for d in docs]


@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: str):
    user_id = get_default_user_id()
    oid = to_object_id(task_id)
    doc = await mongodb.collection("tasks").find_one({"_id": oid, "userId": user_id})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return Task(**doc)


@router.patch("/{task_id}", response_model=Task)
async def update_task(task_id: str, payload: TaskUpdate):
    user_id = get_default_user_id()
    oid = to_object_id(task_id)

    update = payload.model_dump(exclude_unset=True)
    update["updatedAt"] = now_utc()

    if update.get("status") == "done" and "completedAt" not in update:
        update["completedAt"] = now_utc()

    res = await mongodb.collection("tasks").update_one(
        {"_id": oid, "userId": user_id},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    doc = await mongodb.collection("tasks").find_one({"_id": oid, "userId": user_id})
    return Task(**doc)


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    user_id = get_default_user_id()
    oid = to_object_id(task_id)
    res = await mongodb.collection("tasks").delete_one({"_id": oid, "userId": user_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return {"deleted": True}