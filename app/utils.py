from __future__ import annotations

import os
from datetime import datetime, date
from bson import ObjectId
from fastapi import HTTPException, status


def get_default_user_id() -> str:
    # MVP single-user mode
    return os.getenv("DEFAULT_USER_ID", "demo_user")


def now_utc() -> datetime:
    return datetime.utcnow()


def to_object_id(id_str: str) -> ObjectId:
    if not ObjectId.is_valid(id_str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ObjectId")
    return ObjectId(id_str)


def weekday_sun0(d: date) -> int:
    """
    Sunday=0 ... Saturday=6
    Python weekday(): Monday=0 ... Sunday=6
    """
    return (d.weekday() + 1) % 7