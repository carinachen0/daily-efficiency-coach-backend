from __future__ import annotations

from datetime import datetime, date
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, Field, ConfigDict

try:
    from bson import ObjectId
except Exception:  # pragma: no cover
    ObjectId = Any


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        schema.update(type="string")
        return schema


def utcnow() -> datetime:
    return datetime.utcnow()


class MongoBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, PyObjectId: str, datetime: lambda v: v.isoformat()},
    )
    id: Optional[PyObjectId] = Field(default=None, alias="_id")


Priority = Literal["low", "medium", "high"]
TaskStatus = Literal["todo", "in_progress", "done", "skipped"]

HabitTargetType = Literal["binary", "count", "duration"]
HabitScheduleType = Literal["daily", "weekdays", "weekly_x", "custom"]

HabitLogStatus = Literal["done", "missed", "skipped"]


# -------------------------
# TASKS
# -------------------------
class Task(MongoBaseModel):
    userId: Optional[str] = None

    title: str
    description: Optional[str] = None

    status: TaskStatus = "todo"
    priority: Priority = "medium"

    scheduledDate: Optional[date] = None
    dueAt: Optional[datetime] = None

    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    timeSpentSec: Optional[int] = None
    timeEstimateSec: Optional[int] = None

    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None

    createdAt: datetime = Field(default_factory=utcnow)
    updatedAt: datetime = Field(default_factory=utcnow)


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Priority = "medium"
    scheduledDate: Optional[date] = None
    dueAt: Optional[datetime] = None
    timeEstimateSec: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    category: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[Priority] = None
    scheduledDate: Optional[date] = None
    dueAt: Optional[datetime] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    timeSpentSec: Optional[int] = None
    timeEstimateSec: Optional[int] = None
    tags: Optional[List[str]] = None
    category: Optional[str] = None


# -------------------------
# HABITS
# -------------------------
class HabitSchedule(BaseModel):
    type: HabitScheduleType = "daily"
    daysOfWeek: Optional[List[int]] = None  # custom schedule: 0=Sun..6=Sat
    timesPerWeek: Optional[int] = None      # weekly_x


class Habit(MongoBaseModel):
    userId: Optional[str] = None

    name: str
    description: Optional[str] = None
    isActive: bool = True

    targetType: HabitTargetType = "binary"
    targetValue: Optional[float] = None
    targetUnit: Optional[str] = None

    schedule: HabitSchedule = Field(default_factory=HabitSchedule)
    defaultReminderTime: Optional[str] = None  # "HH:MM"
    startDate: Optional[date] = None

    createdAt: datetime = Field(default_factory=utcnow)
    updatedAt: datetime = Field(default_factory=utcnow)


class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    targetType: HabitTargetType = "binary"
    targetValue: Optional[float] = None
    targetUnit: Optional[str] = None
    schedule: HabitSchedule = Field(default_factory=HabitSchedule)
    defaultReminderTime: Optional[str] = None
    startDate: Optional[date] = None


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    isActive: Optional[bool] = None
    targetType: Optional[HabitTargetType] = None
    targetValue: Optional[float] = None
    targetUnit: Optional[str] = None
    schedule: Optional[HabitSchedule] = None
    defaultReminderTime: Optional[str] = None
    startDate: Optional[date] = None


# -------------------------
# HABIT LOGS
# -------------------------
class HabitLog(MongoBaseModel):
    userId: Optional[str] = None
    habitId: PyObjectId

    date: date
    status: HabitLogStatus = "missed"

    value: Optional[float] = None

    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    timeSpentSec: Optional[int] = None

    note: Optional[str] = None

    createdAt: datetime = Field(default_factory=utcnow)
    updatedAt: datetime = Field(default_factory=utcnow)


class HabitLogCreate(BaseModel):
    habitId: str
    date: date
    status: HabitLogStatus = "done"
    value: Optional[float] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    timeSpentSec: Optional[int] = None
    note: Optional[str] = None


class HabitLogUpdate(BaseModel):
    status: Optional[HabitLogStatus] = None
    value: Optional[float] = None
    startedAt: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    timeSpentSec: Optional[int] = None
    note: Optional[str] = None


# -------------------------
# INDEXES
# -------------------------
MONGO_INDEXES = {
    "tasks": [
        {"keys": [("userId", 1), ("scheduledDate", 1)], "unique": False},
        {"keys": [("userId", 1), ("dueAt", 1)], "unique": False},
        {"keys": [("userId", 1), ("status", 1)], "unique": False},
    ],
    "habits": [
        {"keys": [("userId", 1), ("isActive", 1)], "unique": False},
    ],
    "habitLogs": [
        {"keys": [("userId", 1), ("habitId", 1), ("date", 1)], "unique": True},
        {"keys": [("userId", 1), ("date", 1)], "unique": False},
    ],
}