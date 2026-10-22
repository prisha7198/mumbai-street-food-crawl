"""Opening hours, including stalls that close after midnight.

A stall open 18:00-02:30 on a Monday is still serving at 01:00 on Tuesday.
That late-night window belongs to Monday's session, so it is Monday's
closed_day that matters, not Tuesday's.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from . import config
from .models import DAYS, Stall


def to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def now_local() -> datetime:
    return datetime.now(ZoneInfo(config.TIMEZONE))


def resolve_when(time: str | None, day: str | None) -> tuple[int, str]:
    """(minutes since midnight, weekday name) for the request, defaulting to now."""
    now = now_local()
    minutes = to_minutes(time) if time else now.hour * 60 + now.minute
    weekday = day if day in DAYS else DAYS[now.weekday()]
    return minutes, weekday


def previous_day(day: str) -> str:
    return DAYS[(DAYS.index(day) - 1) % 7]


def session_day(stall: Stall, minutes: int, day: str) -> str:
    """The weekday whose session would be serving at this time.

    For 01:00 on Tuesday at a stall open 18:00-02:30, that is Monday.
    """
    o, c = to_minutes(stall.open_time), to_minutes(stall.close_time)
    if c < o and minutes < c:
        return previous_day(day)
    return day


def is_open(stall: Stall, minutes: int, day: str) -> bool:
    o, c = to_minutes(stall.open_time), to_minutes(stall.close_time)
    if o == c:                       # open around the clock
        return stall.closed_day != day
    if o < c:                        # same-day window, e.g. 10:00-22:00
        return o <= minutes < c and stall.closed_day != day
    # window crosses midnight, e.g. 18:00-02:30
    if minutes >= o:                 # evening part, today's session
        return stall.closed_day != day
    if minutes < c:                  # after-midnight part, yesterday's session
        return stall.closed_day != previous_day(day)
    return False


def status(stall: Stall, minutes: int, day: str) -> dict:
    """Small status object for the UI: open now / closes at / opens at."""
    if is_open(stall, minutes, day):
        return {"open": True, "label": f"Closes at {stall.close_time}"}
    if stall.closed_day == day:
        return {"open": False, "label": f"Closed on {day}s"}
    return {"open": False, "label": f"Opens at {stall.open_time}"}
