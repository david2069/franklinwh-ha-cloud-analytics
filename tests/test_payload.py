"""Periods, the chart payload and the fetch, against the franklinwh-cloud response shapes."""
import asyncio
from datetime import date

import pytest

import franklinwh_ha_cloud_analytics as ca

TODAY = date(2026, 11, 9)


# ── periods ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("period,on,want", [
    ("day5", date(2026, 11, 5), date(2026, 11, 5)),
    ("dayhour", date(2026, 11, 5), date(2026, 11, 5)),
    ("week", date(2026, 11, 5), date(2026, 11, 2)),        # Thursday → its Monday
    ("month", date(2026, 11, 5), date(2026, 11, 1)),
    ("year", date(2026, 11, 5), date(2026, 1, 1)),
    ("lifetime", date(2020, 1, 1), TODAY),                  # the date is ignored
])
def test_resolve_snaps_to_the_period_start(period, on, want):
    assert ca.resolve(period, on, TODAY).start == want


def test_navigation_steps_whole_periods_and_stops_at_today():
    assert ca.resolve("month", date(2026, 1, 31), TODAY).prev == date(2025, 12, 1)
    assert ca.resolve("month", date(2026, 10, 31), TODAY).next == date(2026, 11, 1)
    assert ca.resolve("month", date(2026, 11, 5), TODAY).next is None        # no future
    assert ca.resolve("week", date(2026, 11, 5), TODAY).prev == date(2026, 10, 26)
    assert ca.resolve("year", date(2025, 6, 1), TODAY).next == date(2026, 1, 1)
    assert ca.resolve("day5", date(2026, 11, 8), TODAY).next == TODAY
    life = ca.resolve("lifetime", TODAY, TODAY)
    assert life.prev is None and life.next is None


def test_unknown_period_is_refused():
    with pytest.raises(ValueError):
        ca.resolve("ytd", TODAY, TODAY)


# ── kWh periods: bars of the cloud's own totals ──────────────────────────────
MONTH = {"deviceTimeArray": ["2026-11-01", "2026-11-02"],
         "kwhLoadArray": [20.5, None], "kwhSuArray": [30.0, None],
         "kwhGenArray": [0.0, None],
         "kwhFhpDiArray": [8.0, None], "kwhFhpChgArray": [10.0, None],
         "kwhUtiInArray": [2.0, None], "kwhUtiOutArray": [9.5, None]}


def test_kwh_period_is_bars_with_signs_nulls_and_evidence():
    p = ca.build(ca.resolve("month", date(2026, 11, 1), TODAY), MONTH)
    assert p["chart"] == "bars" and p["unit"] == "kWh" and p["source"] == "cloud"
    assert p["labels"] == ["2026-11-01", "2026-11-02"]
    s = {x["key"]: x for x in p["series"]}
    assert s["home"]["values"] == [20.5, None]                   # no data is null, never 0
    assert s["battery_charge"]["values"] == [-10.0, None]        # charge −
    assert s["battery_discharge"]["values"] == [8.0, None]       # discharge +
    assert s["grid_export"]["values"] == [-9.5, None]            # export −
    assert s["grid_import"]["values"] == [2.0, None]             # import +
    assert s["home"]["evidence"] == "CORROBORATED" and s["home"]["derived"] is False
    assert s["generator"]["evidence"] == "INFERRED"
    assert p["empty"] is False
    assert p["date"] == "2026-11-01" and p["nav"] == {"prev": "2026-10-01", "next": None}


def test_a_period_with_no_data_says_empty():
    p = ca.build(ca.resolve("year", date(2027, 1, 1), date(2027, 1, 1)), {})
    assert p["empty"] is True and p["labels"] == []


# ── Day (5-min): lines in kW, home / battery / grid derived from the flows ───
DAY = {"deviceTimeArray": ["2026-11-05 00:00", "2026-11-05 00:05", "2026-11-05 01:00"],
       "powerSolarHomeArray": [1.0, 0.0, None], "powerSolarGirdArray": [0.5, 0.0, 0.0],
       "powerSolarFhpArray": [0.5, 0.0, 0.0], "powerGirdHomeArray": [0.0, 0.2, 0.0],
       "powerGirdFhpArray": [0.0, 1.0, 0.0], "powerFhpHomeArray": [0.0, 0.0, 0.6],
       "powerFhpGirdArray": [0.0, 0.0, 0.0]}


def test_day_5min_lines_are_derived_kw_and_null_when_a_part_is_null():
    p = ca.build(ca.resolve("day5", date(2026, 11, 5), TODAY), DAY)
    assert p["chart"] == "line" and p["unit"] == "kW"
    s = {x["key"]: x for x in p["series"]}
    assert set(s) == {"home", "solar", "battery", "grid"}
    assert s["home"]["values"][:2] == [1.0, 0.2]
    assert s["solar"]["values"][:2] == [2.0, 0.0]
    assert s["battery"]["values"][:2] == [-0.5, -1.0]            # charging −
    assert s["grid"]["values"][:2] == [-0.5, 1.2]                # export −, import +
    assert s["home"]["values"][2] is None                        # solar→home was null
    assert s["home"]["derived"] is True and s["home"]["evidence"] == "CORROBORATED"


def test_day_hourly_integrates_the_5min_flows_into_kwh():
    p = ca.build(ca.resolve("dayhour", date(2026, 11, 5), TODAY), DAY)
    assert p["chart"] == "bars" and p["unit"] == "kWh"
    assert p["labels"][:2] == ["00:00", "01:00"] and len(p["labels"]) == 24
    s = {x["key"]: x for x in p["series"]}
    assert s["home"]["values"][0] == pytest.approx((1.0 + 0.2) / 12)
    assert s["battery_charge"]["values"][0] == pytest.approx(-(0.5 + 1.0) / 12)
    assert s["home"]["values"][2] is None                        # an hour with no samples
    assert s["home"]["derived"] is True
    assert "5-minute" in p["note"]


# ── fetch: the right call, cached ────────────────────────────────────────────
class FakeClient:
    def __init__(self):
        self.calls = []

    async def get_power_details(self, type, timeperiod):
        self.calls.append(("details", type, timeperiod))
        return MONTH

    async def get_power_by_day(self, dayTime):
        self.calls.append(("by_day", dayTime))
        return DAY


def test_fetch_uses_the_library_call_for_each_period_and_caches():
    c, cache = FakeClient(), ca.Cache()
    run = lambda period, on, now=0.0: asyncio.run(
        ca.fetch(c, period, on, today=TODAY, cache=cache, key="gw1", now=now))
    run("week", date(2026, 11, 5))
    run("dayhour", date(2026, 11, 5))
    run("day5", date(2026, 11, 5))                       # same day: cached
    assert c.calls == [("details", 2, "2026-11-02"), ("by_day", "2026-11-05")]
    run("month", date(2026, 11, 5))                      # current month
    run("month", date(2026, 11, 5), now=ca.Cache.CURRENT_S + 1)   # stale → fetched again
    run("month", date(2026, 10, 5))
    run("month", date(2026, 10, 5), now=ca.Cache.CURRENT_S + 1)   # finished month: still cached
    assert c.calls[2:] == [("details", 3, "2026-11-01"), ("details", 3, "2026-11-01"),
                           ("details", 3, "2026-10-01")]
