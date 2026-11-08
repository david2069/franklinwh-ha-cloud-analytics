"""Periods: which library call each needs, the date it is asked for, and its neighbours.

getFhpElectricData honours a week only from its Monday; month and year are snapped to their
first day so stepping never skips or repeats one (franklinwh-cloud
docs/ENERGY_CLI_IMPLEMENTATION_PLAN.md, DEF-ENERGY-PERIOD-PARAM). A Day request returns a
single bucket, so both Day views read the 5-minute power instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: period → getFhpElectricData type, or None for the 5-minute call.
PERIODS: dict[str, int | None] = {
    "day5": None, "dayhour": None, "week": 2, "month": 3, "year": 4, "lifetime": 5}


@dataclass(frozen=True)
class Period:
    name: str
    type: int | None        # None: get_power_by_day
    start: date             # the date the library is asked for
    prev: date | None
    next: date | None       # None when it would be in the future
    current: bool           # today falls inside it


def _start(name: str, on: date, today: date) -> date:
    if name in ("day5", "dayhour"):
        return on
    if name == "week":
        return on - timedelta(days=on.weekday())
    if name == "month":
        return on.replace(day=1)
    if name == "year":
        return on.replace(month=1, day=1)
    return today


def _step(name: str, start: date, n: int) -> date:
    if name in ("day5", "dayhour"):
        return start + timedelta(days=n)
    if name == "week":
        return start + timedelta(weeks=n)
    if name == "month":
        m = start.year * 12 + start.month - 1 + n
        return date(m // 12, m % 12 + 1, 1)
    return start.replace(year=start.year + n)


def resolve(name: str, on: date, today: date) -> Period:
    """The period ``name`` that contains ``on`` (``today`` in the site's zone)."""
    if name not in PERIODS:
        raise ValueError(f"unknown period {name!r}; one of {', '.join(PERIODS)}")
    start = _start(name, on, today)
    if name == "lifetime":
        return Period(name, PERIODS[name], start, None, None, True)
    nxt = _step(name, start, 1)
    return Period(name, PERIODS[name], start, _step(name, start, -1),
                  nxt if nxt <= today else None, start <= today < nxt)
