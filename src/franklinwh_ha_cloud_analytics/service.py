"""The one library call per period, cached so the cloud is asked as little as possible.

franklinwh-cloud has no energy cache of its own and its rate limits are per account
(docs/RATE_LIMITING.md), so a period that is still filling in is kept for a few minutes
and a finished one for hours.
"""
from __future__ import annotations

import time
from datetime import date

from .payload import build
from .periods import resolve


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


async def fetch(client, period: str, on: date, *, today: date, cache: Cache | None = None,
                key: str = "", now: float | None = None) -> dict:
    """The payload for ``period`` containing ``on``. ``client`` is a logged-in
    franklinwh-cloud client for the gateway; ``key`` separates gateways in ``cache``."""
    p = resolve(period, on, today)
    now = time.time() if now is None else now
    call = ("by_day", p.start.isoformat()) if p.type is None \
        else ("details", p.type, p.start.isoformat())
    ck = (key, *call)
    result = cache.get(ck, now) if cache else None
    if result is None:
        result = (await client.get_power_by_day(p.start.isoformat()) if p.type is None
                  else await client.get_power_details(p.type, p.start.isoformat()))
        if cache is not None:
            cache.put(ck, result or {}, Cache.CURRENT_S if p.current else Cache.FINISHED_S, now)
    out = build(p, result)
    out["fetched_at"] = now
    return out
