"""The one library call per period, cached so the cloud is asked as little as possible.

franklinwh-cloud has no energy cache of its own and its rate limits are per account
(docs/RATE_LIMITING.md), so a period that is still filling in is kept for a few minutes
and a finished one for hours.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from .payload import build
from .periods import Period, resolve


class Cache:
    CURRENT_S = 300           # a period today falls in
    FINISHED_S = 6 * 3600     # a period that has ended

    def __init__(self):
        self._d: dict[tuple, tuple[float, float, dict]] = {}

    def get(self, key: tuple, now: float):
        hit = self._d.get(key)
        return hit[2] if hit and now - hit[0] < hit[1] else None

    def put(self, key: tuple, value: dict, ttl: float, now: float) -> None:
        self._d[key] = (now, ttl, value)


async def _result(client, p, cache: Cache | None, key: str, now: float) -> dict:
    """The library's reply for period ``p``, from ``cache`` while it is fresh."""
    call = ("by_day", p.start.isoformat()) if p.type is None \
        else ("details", p.type, p.start.isoformat())
    ck = (key, *call)
    result = cache.get(ck, now) if cache else None
    if result is None:
        result = (await client.get_power_by_day(p.start.isoformat()) if p.type is None
                  else await client.get_power_details(p.type, p.start.isoformat()))
        if cache is not None:
            cache.put(ck, result or {}, Cache.CURRENT_S if p.current else Cache.FINISHED_S, now)
    return result or {}


async def fetch(client, period: str, on: date, *, today: date, cache: Cache | None = None,
                key: str = "", now: float | None = None) -> dict:
    """The payload for ``period`` containing ``on``. ``client`` is a logged-in
    franklinwh-cloud client for the gateway; ``key`` separates gateways in ``cache``."""
    p = resolve(period, on, today)
    now = time.time() if now is None else now
    out = build(p, await _result(client, p, cache, key, now))
    out["fetched_at"] = now
    return out


#: A custom range's slots by its length: (longest span in days, slot, the period read per piece).
RANGE_STEPS = ((2, "5min", "day5"), (31, "hour", "dayhour"), (366, "day", "month"))


def range_res(start: datetime, end: datetime) -> tuple[str, str]:
    """(slot, period read per piece) for a range: 5-minute power to 2 days, hourly kWh to
    31 days, daily to a year, monthly beyond."""
    days = (end - start).total_seconds() / 86400
    for most, res, period in RANGE_STEPS:
        if days <= most:
            return res, period
    return "month", "year"


async def fetch_range(client, start: datetime, end: datetime, *, today: date,
                      cache: Cache | None = None, key: str = "", now: float | None = None) -> dict:
    """The payload for the site-local range ``start`` to ``end`` (end not included): the
    replies for each day, month or year in it (none after ``today``, each cached as
    :func:`fetch` caches it), joined, trimmed to the range and built as one period."""
    if end <= start:
        raise ValueError("the range must end after it starts")
    now = time.time() if now is None else now
    res, period = range_res(start, end)
    pieces, on = [], start.date()
    while on <= (end - timedelta(microseconds=1)).date() and on <= today:
        p = resolve(period, on, today)
        pieces.append((p, await _result(client, p, cache, key, now)))
        if p.next is None:          # the next one would be after today
            break
        on = p.next
    merged = _join(pieces, res, start, end)
    first = resolve(period, start.date(), today)
    build_as = Period("dayhour" if res == "hour" else period, first.type, start.date(), None, None,
                      end > datetime.combine(today, datetime.min.time()))
    out = build(build_as, merged, dated_hours=res == "hour")
    out.update(period="custom", res=res, nav=None, date=start.date().isoformat(),
               current=build_as.current, fetched_at=now,
               **{"from": start.strftime("%Y-%m-%dT%H:%M"), "to": end.strftime("%Y-%m-%dT%H:%M")})
    if res == "hour":
        out["note"] = ("Hourly kWh added up from the 5-minute power, within about 3% of the "
                       "days' own totals.")
    return out


def _keep(label: str, res: str, start: datetime, end: datetime) -> bool:
    t = str(label)
    if res in ("5min", "hour"):
        at = datetime.fromisoformat(t[:16].replace(" ", "T"))
        if res == "hour":
            return start.replace(minute=0, second=0, microsecond=0) <= at < end
        return start <= at < end
    if res == "day":
        d = datetime.fromisoformat(t[:10])
        return start.replace(hour=0, minute=0, second=0, microsecond=0) <= d < end
    m = datetime(int(t[:4]), int(t[5:7]), 1)
    return start.replace(day=1, hour=0, minute=0, second=0, microsecond=0) <= m < end


def _join(pieces, res: str, start: datetime, end: datetime) -> dict:
    """One reply from many: every array cut to the labels inside the range, in order; an
    array a piece lacks is padded with None so the columns stay aligned."""
    keys = {k for _, r in pieces for k, v in r.items() if isinstance(v, list)} - {"deviceTimeArray"}
    out: dict[str, list] = {"deviceTimeArray": []}
    for k in keys:
        out[k] = []
    for _, r in pieces:
        labels = list(r.get("deviceTimeArray") or [])
        idx = [i for i, t in enumerate(labels) if _keep(t, res, start, end)]
        out["deviceTimeArray"] += [str(labels[i])[:7] if res == "month" else labels[i] for i in idx]
        for k in keys:
            arr = r.get(k)
            out[k] += [arr[i] if isinstance(arr, list) and i < len(arr) else None for i in idx]
    return out
