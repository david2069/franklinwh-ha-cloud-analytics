"""Insights (direct-connect-bridge #588): trends against earlier periods, and the setup to
change for the user's objectives, each with its numbers, why, and an estimated effect.
Rules only; no model, no I/O."""
import pytest

from franklinwh_ha_cloud_analytics import insights as ins

# A 30-day month: 600 kWh home, 450 solar, 250 imported, 150 exported, battery 60/62.
MONTH = dict(days=30, home=600.0, solar=450.0, grid_import=250.0, grid_export=150.0,
             battery_discharge=60.0, battery_charge=62.0)
SITE = dict(mode="self", reserve_pct=20, capacity_kwh=13.6, solar_kwp=6.6,
            tariff={"kind": "tou", "buy_c": 35.0, "sell_c": 5.0, "peak": ["15:00-21:00"]})


def _ids(items):
    return [x["id"] for x in items]


# ── ratios ────────────────────────────────────────────────────────────────────
def test_ratios_from_the_totals():
    r = ins.ratios(MONTH, capacity_kwh=13.6)
    assert r["self_sufficiency"] == pytest.approx(1 - 250 / 600)
    assert r["solar_used"] == pytest.approx(1 - 150 / 450)
    assert r["cycles_per_day"] == pytest.approx(60 / 13.6 / 30)


def test_no_data_stays_none_never_zero():
    r = ins.ratios(dict(days=30, home=None, solar=0.0, grid_import=None, grid_export=0.0,
                        battery_discharge=None, battery_charge=None))
    assert r["self_sufficiency"] is None and r["solar_used"] is None
    assert r["cycles_per_day"] is None


# ── trends ────────────────────────────────────────────────────────────────────
def test_trend_against_the_previous_period_and_last_year():
    prev = {**MONTH, "grid_import": 200.0}
    last_year = {**MONTH, "grid_import": 300.0}
    t = {x["id"]: x for x in ins.trends(MONTH, previous=prev, last_year=last_year)}
    imp = t["grid_import"]
    assert imp["vs_previous"] == pytest.approx(0.25) and imp["direction"] == "up"
    assert imp["vs_last_year"] == pytest.approx(250 / 300 - 1)
    assert "25%" in imp["headline"] and "previous" in imp["headline"]


def test_small_changes_are_steady():
    t = {x["id"]: x for x in ins.trends(MONTH, previous={**MONTH, "home": 610.0})}
    assert t["home"]["direction"] == "steady"


def test_periods_of_different_length_compare_per_day():
    prev = {**MONTH, "days": 31, "home": 620.0}               # same per day
    t = {x["id"]: x for x in ins.trends(MONTH, previous=prev)}
    assert t["home"]["direction"] == "steady"


def test_a_falling_streak_is_named():
    hist = [{**MONTH, "grid_import": g} for g in (150.0, 180.0, 210.0)]   # oldest first
    t = {x["id"]: x for x in ins.trends(MONTH, history=hist)}
    ss = t["self_sufficiency"]
    assert ss["streak"] == 3 and ss["direction"] == "down"
    assert "3 periods running" in ss["headline"]


def test_no_baseline_no_trend():
    assert ins.trends(MONTH) == [] or all(x.get("vs_previous") is None for x in ins.trends(MONTH))


# ── suggestions for the objectives ───────────────────────────────────────────
def test_backup_mode_idling_suggests_self_consumption_for_self_sufficiency():
    s = ins.suggest({**MONTH, "battery_discharge": 3.0, "battery_charge": 3.5},
                    {**SITE, "mode": "backup"}, ["self_sufficiency"])
    top = s[0]
    assert top["id"] == "backup_to_self" and top["action"] == {"type": "mode", "mode": "self",
                                                              "reserve_pct": 20}
    assert top["effect"]["kwh_month"] > 0 and top["effect"]["estimate"] is True
    assert top["numbers"]["cycles_per_day"] < 0.1 and top["why"]


def test_tou_tariff_in_self_consumption_suggests_tou_for_lowest_bill_with_money():
    s = {x["id"]: x for x in ins.suggest(MONTH, SITE, ["lowest_bill"])}
    assert "self_to_tou" in s
    assert s["self_to_tou"]["action"]["type"] == "mode" and s["self_to_tou"]["action"]["mode"] == "tou"


def test_money_needs_prices():
    site = {**SITE, "mode": "backup", "tariff": None}
    s = ins.suggest({**MONTH, "battery_discharge": 3.0}, site, ["lowest_bill"])
    assert s and all(x["effect"].get("money_month") is None for x in s)


def test_backup_ready_raises_a_low_reserve():
    s = {x["id"]: x for x in ins.suggest(MONTH, {**SITE, "reserve_pct": 10}, ["backup_ready"])}
    assert s["raise_reserve"]["action"] == {"type": "reserve", "reserve_pct": 30}


def test_battery_care_flags_heavy_cycling():
    heavy = {**MONTH, "battery_discharge": 13.6 * 1.3 * 30}
    s = {x["id"]: x for x in ins.suggest(heavy, SITE, ["battery_care"])}
    assert "heavy_cycling" in s


def test_suggestions_only_for_the_chosen_objectives():
    s = ins.suggest(MONTH, {**SITE, "reserve_pct": 10}, ["self_sufficiency"])
    assert "raise_reserve" not in _ids(s)


def test_unknown_objective_is_refused():
    with pytest.raises(ValueError):
        ins.suggest(MONTH, SITE, ["world_peace"])


# ── the one call ─────────────────────────────────────────────────────────────
def test_summarise_returns_the_three_parts_as_plain_data():
    out = ins.summarise(MONTH, previous={**MONTH, "grid_import": 200.0}, site=SITE,
                        objectives=["lowest_bill"])
    assert set(out) == {"ratios", "trends", "findings", "suggestions", "objectives"}
    import json
    json.dumps(out)                                            # MCP / API ready
    for item in out["trends"] + out["findings"] + out["suggestions"]:
        assert {"id", "kind", "headline", "why"} <= set(item)
