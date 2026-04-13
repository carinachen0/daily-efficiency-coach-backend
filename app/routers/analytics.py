from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, date as Date
from zoneinfo import ZoneInfo # for time block behavior
from fastapi import APIRouter, Query

from app.db import mongodb
from app.utils import get_default_user_id, to_object_id, weekday_sun0

router = APIRouter()

USER_TZ = ZoneInfo("America/New_York") # placeholder, can swap in for users TZ or default use EST

TIME_BLOCKS = {
    "midnight": (0,5),
    "early_morning": (5,9),
    "morning": (9,12),
    "afternoon": (12,17),
    "evening": (17,21),
    "night": (21,24),
}

WEEKDAYS = [ "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] # converts integer to string

# Behavior pattern threshold
MIN_TASKS = 5      # minimum task in window to even generate insights, easier to hit in early usage
MIN_COMPLETIONS = 5  # minimum completions for productive day/time block insights

def get_time_block(dt:datetime)-> str:
    hour = dt.hour
    for block, (start,end) in TIME_BLOCKS.items():
        if start <= hour < end:
            return block
    return "night" 

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


@router.get("/tasks/delays")
async def task_delays(days: int = Query(default=7, ge=1, le=365)):
    """
    How many tasks were completed on time vs late :
      Late = completedAT > dueAt
    """
    user_id = get_default_user_id()
    start_dt = datetime.utcnow() - timedelta(days=days)
    
    # fetch and analyze tasks that have a due date 
    completed_tasks = await mongodb.collection("tasks").find(
        {"userId": user_id, "status": "done", "completedAt": {"$gte": start_dt}, "dueAt": {"$exists": True, "$ne": None}}
    ).to_list(length=500)
    
    on_time = 0
    late = 0
    total_delay_seconds = 0
    
    for task in completed_tasks:
        due = task["dueAt"]
        completed = task["completedAt"]
        if completed <= due:
            on_time += 1
        else:
            late += 1
            total_delay_seconds += (completed-due).total_seconds()
    
    # Divide total delay seconds by number of late tasks to get average; convert to days
    avg_delay_days = (total_delay_seconds / late / 86400) if late else 0 
    
    return {
        "windowDays": days,
        "onTime": on_time,
        "late": late,
        "avgDelayDays": round(avg_delay_days, 2)       
    }

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
        {"userId": user_id, "status": "done", "createdAt": {"$gte": start_dt}}
    )

    return {
        "windowDays": days,
        "created": created,
        "completed": completed,
        "completionRate": (completed / created) if created else None,
    }

@router.get("/tasks/behavior-patterns")
async def task_behavior_patterns(days: int = Query(default=7, ge=1, le=365)):
    """
    Detects behavioral patterns over the last N days
     - most skipped / postponed tasks (grouped by category; skip uncategorized tasks)
     - most productive day of the week (based on most completions)
     - most productive time of the day (based on completedAt hour)
     - tasks most often completed late (completedAt > dueAt)
    """
    user_id = get_default_user_id()
    start_dt = datetime.utcnow() - timedelta(days=days)
    
    tasks = await mongodb.collection("tasks"). find(
        {"userId": user_id, "$or": [
        {"createdAt": {"$gte": start_dt}},
        {"completedAt": {"$gte": start_dt}}
    ]}
    ).to_list(length=1000)
    
    # Global sufficiency check (end early if not enough data to generate insights)
    if len(tasks) < MIN_TASKS:
        return {
            "windowDays": days,
            "insufficientData": True,
            "reason": f"Need at least {MIN_TASKS} tasks in the window (found {len(tasks)})",
        }
        
    #initialize counters
    skip_counts: dict[str, int] = defaultdict(int)
    postpone_counts: dict[str, int] = defaultdict(int)
    day_counts: dict[int,int] = defaultdict(int) # 0=sun...6=sat
    block_counts: dict[str,int] = defaultdict(int)
    late_counts: dict[str,int] =defaultdict(int)
    
    for t in tasks:
        category = t.get("category")
        status = t.get("status")
        completed_at = t.get("completedAt")
        due_at = t.get("dueAt")
        
        # skipped or postponed (with category only)
        if category: 
            if status == "skipped":
                skip_counts[category]+= 1
            elif status == "postponed":
                postpone_counts[category]+= 1
        
        # calculate productive day & time block & late (done tasks only)
        if status == "done" and isinstance(completed_at, datetime):
            local_dt = completed_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(USER_TZ)
            day_counts[weekday_sun0(local_dt.date())]+= 1 
            block_counts[get_time_block(local_dt)] += 1
            if category and isinstance(due_at, datetime) and completed_at > due_at:
                late_counts[category] += 1
    
    #creates list of category-count pairs, sort list based on count value in descending order, return top 3
    most_skipped = sorted(
        [{"category": k, "count": v} for k,v in skip_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:3]
    
    most_postponed = sorted(
        [{"category": k, "count": v} for k,v in postpone_counts.items()],
        key=lambda x: x["count"], reverse=True
    )[:3]
               
    productive_days = sorted(
        [{"day": WEEKDAYS[i], "completions": day_counts.get(i,0)} for i in range(7)], 
        key=lambda x: x["completions"], reverse=True
    )
        
    productive_blocks = sorted(
        [{"time_block": block, "completions": block_counts.get(block, 0)} for block in TIME_BLOCKS.keys()], 
        key=lambda x: x["completions"], reverse=True
    )

    most_late = sorted(
        [{"category": k, "times_late": v} for k,v in late_counts.items()],
        key=lambda x: x["times_late"], reverse=True
    )[:3]
    
    # top insights (none if there is not enough completions)
    total_completions = sum(day_counts.values())
    
    most_productive_day = (
        productive_days[0]["day"] 
        if total_completions >= MIN_COMPLETIONS
        else None
    )
    
    most_productive_block = (
        productive_blocks[0]["time_block"] 
        if total_completions >= MIN_COMPLETIONS
        else None
    )
        
    return {
        "windowDays" : days,
        "insufficientData": False,
        "mostSkipped": most_skipped,
        "mostPostponed": most_postponed,
        "productiveDays": productive_days,
        "mostProductiveDay": most_productive_day,
        "productiveBlocks": productive_blocks,
        "mostProductiveBlock": most_productive_block,
        "mostLate": most_late,
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
        
        # convert date to datetime for MongoDB query
        day_dt = datetime.combine(day, datetime.min.time())
    
        log = await mongodb.collection("habitLogs").find_one(
            {"userId": user_id, "habitId": hid, "date": day_dt}
        )
        if log and log.get("status") == "done":
            streak += 1
        else:
            break

    return {"habitId": habit_id, "streak": streak}