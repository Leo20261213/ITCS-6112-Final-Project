"""US-20: As an administrator, I want a dashboard of ticket volumes, statuses, and resolution
trends so that I can monitor support performance.

Metrics are computed from ticket records: created_at gives volume, status gives the
current breakdown, and resolved_at gives resolution time. Managers can view it too.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..access import OVERSIGHT_ROLES
from ..database import get_db
from ..models import Category, Priority, Role, Status, Ticket, User
from ..security import require_roles

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

ACTIVE = (Status.OPEN, Status.IN_PROGRESS, Status.ON_HOLD)


class Totals(BaseModel):
    created: int
    resolved: int
    open_backlog: int
    unassigned: int
    critical_open: int
    median_resolution_hours: float | None
    resolved_within_24h_pct: float | None
    created_change_pct: float | None  # vs the previous period of the same length


class DayPoint(BaseModel):
    date: date
    created: int
    resolved: int


class WeekPoint(BaseModel):
    week_start: date
    resolved: int
    median_resolution_hours: float | None


class CountRow(BaseModel):
    key: str
    label: str
    count: int


class PriorityRow(CountRow):
    median_resolution_hours: float | None


class AgentRow(BaseModel):
    id: int
    name: str
    active: int
    resolved: int
    median_resolution_hours: float | None


class AnalyticsOut(BaseModel):
    days: int
    start: date
    end: date
    totals: Totals
    daily: list[DayPoint]
    weekly: list[WeekPoint]
    by_status: list[CountRow]
    by_priority: list[PriorityRow]
    by_category: list[CountRow]
    agents: list[AgentRow]


STATUS_LABELS = {Status.OPEN: "Open", Status.IN_PROGRESS: "In progress", Status.ON_HOLD: "On hold",
                 Status.RESOLVED: "Resolved", Status.CLOSED: "Closed"}
PRIORITY_LABELS = {Priority.LOW: "Low", Priority.MEDIUM: "Medium", Priority.HIGH: "High", Priority.CRITICAL: "Critical"}


def _utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _hours(t: Ticket) -> float:
    return max(0.0, (_utc(t.resolved_at) - _utc(t.created_at)).total_seconds() / 3600)


def _median(values: list[float]) -> float | None:
    return round(median(values), 1) if values else None


@router.get("", response_model=AnalyticsOut)
def analytics(
    days: int = Query(30, ge=7, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*OVERSIGHT_ROLES)),
):
    now = datetime.now(timezone.utc)
    end = now.date()
    start = end - timedelta(days=days - 1)
    start_dt = datetime.combine(start, datetime.min.time(), timezone.utc)
    prev_start_dt = start_dt - timedelta(days=days)

    tickets = list(db.scalars(select(Ticket)))
    created_in = [t for t in tickets if _utc(t.created_at) >= start_dt]
    created_prev = [t for t in tickets if prev_start_dt <= _utc(t.created_at) < start_dt]
    resolved_in = [t for t in tickets if t.resolved_at and _utc(t.resolved_at) >= start_dt]
    res_hours = [_hours(t) for t in resolved_in]

    # Daily volume: created vs resolved
    created_by_day = Counter(_utc(t.created_at).date() for t in created_in)
    resolved_by_day = Counter(_utc(t.resolved_at).date() for t in resolved_in)
    daily = [
        DayPoint(date=d, created=created_by_day[d], resolved=resolved_by_day[d])
        for d in (start + timedelta(days=i) for i in range(days))
    ]

    # Weekly resolution trend (weeks start on Monday)
    weeks: dict[date, list[float]] = defaultdict(list)
    first_week = start - timedelta(days=start.weekday())
    for t in resolved_in:
        d = _utc(t.resolved_at).date()
        weeks[d - timedelta(days=d.weekday())].append(_hours(t))
    weekly = []
    w = first_week
    while w <= end:
        weekly.append(WeekPoint(week_start=w, resolved=len(weeks[w]), median_resolution_hours=_median(weeks[w])))
        w += timedelta(days=7)

    status_counts = Counter(t.status for t in tickets)
    by_status = [CountRow(key=s.value, label=STATUS_LABELS[s], count=status_counts[s]) for s in Status]

    by_priority = []
    for p in Priority:
        hours = [_hours(t) for t in resolved_in if t.priority == p]
        by_priority.append(PriorityRow(
            key=p.value, label=PRIORITY_LABELS[p], count=sum(1 for t in created_in if t.priority == p),
            median_resolution_hours=_median(hours),
        ))

    cat_counts = Counter(t.category_id for t in created_in)
    categories = {c.id: c for c in db.scalars(select(Category))}
    by_category = sorted(
        (CountRow(key=str(cid), label=categories[cid].name, count=n) for cid, n in cat_counts.items() if cid in categories),
        key=lambda r: (-r.count, r.label),
    )

    agents = []
    for a in db.scalars(select(User).where(User.role == Role.AGENT).order_by(User.full_name)):
        mine = [t for t in resolved_in if t.assigned_to_id == a.id]
        agents.append(AgentRow(
            id=a.id, name=a.full_name + ("" if a.is_active else " (inactive)"),
            active=sum(1 for t in tickets if t.assigned_to_id == a.id and t.status in ACTIVE),
            resolved=len(mine), median_resolution_hours=_median([_hours(t) for t in mine]),
        ))

    totals = Totals(
        created=len(created_in),
        resolved=len(resolved_in),
        open_backlog=sum(1 for t in tickets if t.status in ACTIVE),
        unassigned=sum(1 for t in tickets if t.status in ACTIVE and t.assigned_to_id is None),
        critical_open=sum(1 for t in tickets if t.status in ACTIVE and t.priority == Priority.CRITICAL),
        median_resolution_hours=_median(res_hours),
        resolved_within_24h_pct=round(100 * sum(h <= 24 for h in res_hours) / len(res_hours), 1) if res_hours else None,
        created_change_pct=round(100 * (len(created_in) - len(created_prev)) / len(created_prev), 1) if created_prev else None,
    )
    return AnalyticsOut(
        days=days, start=start, end=end, totals=totals, daily=daily, weekly=weekly,
        by_status=by_status, by_priority=by_priority, by_category=by_category, agents=agents,
    )
