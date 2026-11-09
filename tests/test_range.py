"""A custom From-To range (owner, 2026-11-10): the cloud's day, month or year replies joined
and trimmed to the range, slots coarser as it grows (5-min to 2 days, hourly to 31 days,
daily to a year, monthly beyond), built like any other period."""
import asyncio
from datetime import date, datetime

import pytest

import franklinwh_ha_cloud_analytics as ca

TODAY = date(2026, 11, 9)


def _day(on):
    t = [f"{on.isoformat()} {h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)]
    n = len(t)
    return {"deviceTimeArray": t, "powerSolarHomeArray": [1.2] * n, "powerFhpHomeArray": [0.6] * n,
            "powerGirdHomeArray": [0.0] * n, "powerSolarFhpArray": [0.0] * n,
            "powerSolarGirdArray": [0.0] * n, "powerGirdFhpArray": [0.0] * n,
            "powerFhpGirdArray": [0.0] * n, "socArray": [50.0] * n}


def _month(first):
    nxt = date(first.year + first.month // 12, first.month % 12 + 1, 1)
    labels = [date.fromordinal(o).isoformat() for o in range(first.toordinal(), nxt.toordinal())]
    n = len(labels)
    return {"deviceTimeArray": labels, "kwhLoadArray": [10.0] * n, "kwhSuArray": [20.0] * n,
            "kwhSolarLoadArray": [6.0] * n}


def _year(first):
    labels = [f"{first.year}-{m:02d}" for m in range(1, 13)]
    return {"deviceTimeArray": labels, "kwhLoadArray": [300.0] * 12, "kwhSuArray": [600.0] * 12}


class Client:
    def __init__(self):
        self.calls = []

    async def get_power_by_day(self, day):
        self.calls.append(("by_day", day))
        return _day(date.fromisoformat(day))

    async def get_power_details(self, type, on):
        self.calls.append(("details", type, on))
        d = date.fromisoformat(on)
        return _month(d) if type == 3 else _year(d)


def run(c, start, end, cache=None):
    return asyncio.run(ca.fetch_range(c, start, end, today=TODAY, cache=cache, key="gw"))


def test_up_to_two_days_is_five_minute_power_across_midnight():
    c = Client()
    p = run(c, datetime(2026, 11, 5, 22, 0), datetime(2026, 11, 6, 2, 0))
    assert c.calls == [("by_day", "2026-11-05"), ("by_day", "2026-11-06")]
    assert p["period"] == "custom" and p["res"] == "5min" and p["unit"] == "kW" and p["chart"] == "line"
    assert p["labels"][0] == "2026-11-05 22:00" and p["labels"][-1] == "2026-11-06 01:55"
    assert len(p["labels"]) == 48
    assert p["from"] == "2026-11-05T22:00" and p["to"] == "2026-11-06T02:00" and p["nav"] is None
    home = next(s for s in p["series"] if s["key"] == "home")
    assert len(home["values"]) == 48
    # flows: 4 h of 1.2 kW solar → home = 4.8 kWh
    assert p["flows"]["solar_to_home"] == pytest.approx(4.8)


def test_up_to_31_days_is_hourly_kwh_with_the_date_in_each_label():
    c = Client()
    p = run(c, datetime(2026, 11, 1, 6, 0), datetime(2026, 11, 4, 6, 0))
    assert p["res"] == "hour" and p["unit"] == "kWh"
    assert len(c.calls) == 4                                        # 1st to 4th Nov
    assert p["labels"][0] == "2026-11-01 06:00" and p["labels"][-1] == "2026-11-04 05:00"
    assert len(p["labels"]) == 72
    home = next(s for s in p["series"] if s["key"] == "home")
    assert home["values"][0] == pytest.approx(1.8)                 # 1.2 + 0.6 kW for an hour


def test_up_to_a_year_is_daily_from_the_month_replies():
    c = Client()
    p = run(c, datetime(2026, 9, 20), datetime(2026, 11, 3))
    assert p["res"] == "day" and c.calls == [("details", 3, "2026-09-01"), ("details", 3, "2026-10-01"),
                                             ("details", 3, "2026-11-01")]
    assert p["labels"][0] == "2026-09-20" and p["labels"][-1] == "2026-11-02" and len(p["labels"]) == 44
    assert p["flows"]["solar_to_home"] == pytest.approx(6.0 * 44)


def test_beyond_a_year_is_monthly_from_the_year_replies():
    c = Client()
    p = run(c, datetime(2024, 6, 1), datetime(2026, 3, 1))
    assert p["res"] == "month" and [x[2] for x in c.calls] == ["2024-01-01", "2025-01-01", "2026-01-01"]
    assert p["labels"][0] == "2024-06" and p["labels"][-1] == "2026-02" and len(p["labels"]) == 21


def test_days_after_today_are_not_asked_for_and_reads_are_cached():
    c, cache = Client(), ca.Cache()
    run(c, datetime(2026, 11, 8, 12), datetime(2026, 11, 11), cache)
    assert c.calls == [("by_day", "2026-11-08"), ("by_day", "2026-11-09")]
    run(c, datetime(2026, 11, 8, 12), datetime(2026, 11, 11), cache)
    assert len(c.calls) == 2


def test_a_range_must_run_forwards():
    with pytest.raises(ValueError):
        run(Client(), datetime(2026, 11, 6), datetime(2026, 11, 5))


def test_a_host_can_ask_for_hourly_slots_on_a_short_range():
    # the DC bridge's Day (hourly) with a From-To keeps its hours (owner, 2026-11-10)
    c = Client()
    p = asyncio.run(ca.fetch_range(c, datetime(2026, 11, 5, 6), datetime(2026, 11, 5, 10), today=TODAY, res="hour"))
    assert p["res"] == "hour" and p["labels"] == ["2026-11-05 06:00", "2026-11-05 07:00", "2026-11-05 08:00", "2026-11-05 09:00"]
    with pytest.raises(ValueError):
        asyncio.run(ca.fetch_range(c, datetime(2026, 11, 5, 6), datetime(2026, 11, 5, 10), today=TODAY, res="week"))
