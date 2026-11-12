"""Insights: what a period's energy says, how it is trending, and what to change for the
user's objectives (direct-connect-bridge #588).

Pure functions over plain data, so a bridge's API, its Explain dialog and an MCP tool give
the same answer. Fixed rules, no model and no I/O. Every item carries its numbers and why;
an effect worked out from the period's own totals is marked ``estimate``. A value the
input doesn't have stays ``None``, never 0, and a rule that needs it says nothing.

Totals are a period's kWh as positive numbers, keyed as in the chart payload: ``home``,
``solar``, ``grid_import``, ``grid_export``, ``battery_discharge``, ``battery_charge``,
plus ``days`` (the period's length). The site is ``mode`` ("tou" | "self" | "backup"),
``reserve_pct``, ``capacity_kwh``, ``solar_kwp`` and ``tariff``: ``{"kind": "flat" |
"tou" | "dynamic", "buy_c", "sell_c", "peak": ["HH:MM-HH:MM", …]}`` in c/kWh.
"""
from __future__ import annotations

OBJECTIVES = {
    "lowest_bill": "Lowest bill",
    "self_sufficiency": "Most self-sufficiency",
    "backup_ready": "Backup ready",
    "export_earnings": "Most export earnings",
    "battery_care": "Battery care",
}

#: Trend metrics: key → (label, kind). "kwh" compares per day; "ratio" in points.
_METRICS = (("home", "Home load", "kwh"), ("solar", "Solar", "kwh"),
            ("grid_import", "Grid imported", "kwh"), ("grid_export", "Grid exported", "kwh"),
            ("battery_discharge", "Battery discharged", "kwh"),
            ("self_sufficiency", "Self-sufficiency", "ratio"),
            ("solar_used", "Solar used on site", "ratio"))
#: Below these a change is "steady": 10% for energy, 3 points for a share.
_STEADY_KWH, _STEADY_PTS = 0.10, 0.03
_MODES = {"tou": "Time-of-Use", "self": "Self-Consumption", "backup": "Emergency Backup"}
_DAYS_PER_MONTH = 30
#: The reserve a "backup ready" site keeps, and the floor a suggestion never goes below.
_BACKUP_RESERVE, _MIN_RESERVE = 30, 20


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _days(t) -> float | None:
    d = _num((t or {}).get("days"))
    return d if d and d > 0 else None


def ratios(totals: dict, capacity_kwh: float | None = None) -> dict:
    """Self-sufficiency, solar used on site and battery cycles a day; None when a part is
    missing (or zero where it would divide)."""
    t = totals or {}
    home, imp = _num(t.get("home")), _num(t.get("grid_import"))
    solar, exp = _num(t.get("solar")), _num(t.get("grid_export"))
    dis, cap, days = _num(t.get("battery_discharge")), _num(capacity_kwh), _days(t)
    return {
        "self_sufficiency": (max(0.0, 1 - imp / home)
                             if home and imp is not None else None),
        "solar_used": max(0.0, 1 - exp / solar) if solar and exp is not None else None,
        "cycles_per_day": dis / cap / days if dis is not None and cap and days else None,
    }


def _value(t: dict, key: str, kind: str):
    if not t:
        return None
    if kind == "ratio":
        return ratios(t)[key]
    v, d = _num(t.get(key)), _days(t)
    return v / d if v is not None and d else None


def _change(now, then, kind):
    if now is None or then is None:
        return None
    if kind == "ratio":
        return now - then
    return now / then - 1 if then else None


def _direction(ch, kind):
    if ch is None:
        return None
    if abs(ch) < (_STEADY_PTS if kind == "ratio" else _STEADY_KWH):
        return "steady"
    return "up" if ch > 0 else "down"


def _say(ch, kind):
    return f"{abs(ch) * 100:.0f} points" if kind == "ratio" else f"{abs(ch) * 100:.0f}%"


def trends(current: dict, *, previous: dict | None = None, last_year: dict | None = None,
           history: list[dict] | None = None) -> list[dict]:
    """Each metric against the previous period and the same period last year (per day,
    so a 31-day month compares with a 30-day one). ``history`` is earlier periods, oldest
    first; its last one stands in for ``previous`` and it names a run of rises or falls."""
    hist = list(history or [])
    prev = previous if previous is not None else (hist[-1] if hist else None)
    if prev is None and last_year is None:
        return []
    out = []
    for key, label, kind in _METRICS:
        now = _value(current, key, kind)
        if now is None:
            continue
        vs_prev = _change(now, _value(prev, key, kind), kind)
        vs_year = _change(now, _value(last_year, key, kind), kind)
        if vs_prev is None and vs_year is None:
            continue
        direction = _direction(vs_prev if vs_prev is not None else vs_year, kind)
        series = [_value(h, key, kind) for h in hist] + [now]
        streak = 0
        if direction in ("up", "down") and len(series) > 2:
            for a, b in zip(reversed(series[:-1]), reversed(series)):
                step = _direction(_change(b, a, kind), kind)
                if a is None or step != direction:
                    break
                streak += 1
        parts = []
        if vs_prev is not None:
            parts.append("steady on the previous period" if _direction(vs_prev, kind) == "steady"
                         else f"{'up' if vs_prev > 0 else 'down'} {_say(vs_prev, kind)} on the "
                              "previous period")
        if vs_year is not None:
            parts.append("steady on last year" if _direction(vs_year, kind) == "steady"
                         else f"{'up' if vs_year > 0 else 'down'} {_say(vs_year, kind)} on "
                              "last year")
        if streak >= 2:
            parts.append(f"{'rising' if direction == 'up' else 'falling'} {streak} periods running")
        out.append({
            "id": key, "kind": "trend", "direction": direction, "streak": streak,
            "vs_previous": vs_prev, "vs_last_year": vs_year,
            "headline": f"{label} {', '.join(parts)}",
            "numbers": {"now": now, "unit": "share" if kind == "ratio" else "kWh/day"},
            "why": ("Per day, so periods of different lengths compare." if kind == "kwh"
                    else "In percentage points of the period's total."),
        })
    return out


def findings(current: dict, site: dict | None = None) -> list[dict]:
    """What the period shows, whatever the objective."""
    site = site or {}
    r = ratios(current, site.get("capacity_kwh"))
    days = _days(current)
    out = []
    if r["self_sufficiency"] is not None:
        out.append({"id": "self_sufficiency", "kind": "finding",
                    "headline": f"{r['self_sufficiency'] * 100:.0f}% of the home's energy came "
                                "from solar and the battery",
                    "numbers": {"self_sufficiency": r["self_sufficiency"]},
                    "why": "1 − grid imported / home load."})
    if r["solar_used"] is not None and r["solar_used"] < 0.7:
        out.append({"id": "solar_exported", "kind": "finding",
                    "headline": f"{(1 - r['solar_used']) * 100:.0f}% of the solar went to the grid",
                    "numbers": {"solar_used": r["solar_used"]},
                    "why": "Grid exported / solar. Stored or used at home it would replace imports."})
    if r["cycles_per_day"] is not None:
        c = r["cycles_per_day"]
        word = "barely used" if c < 0.2 else ("heavily cycled" if c > 1.0 else "in daily use")
        out.append({"id": "battery_use", "kind": "finding",
                    "headline": f"The battery did {c:.2f} cycles a day ({word})",
                    "numbers": {"cycles_per_day": c, "days": days},
                    "why": "Battery discharged / capacity / days."})
    mode = site.get("mode")
    if mode in _MODES:
        out.append({"id": "mode", "kind": "finding",
                    "headline": f"The gateway runs in {_MODES[mode]}",
                    "numbers": {"mode": mode, "reserve_pct": site.get("reserve_pct")},
                    "why": "From the gateway now; the cloud keeps no history of modes."})
    return out


def _money(kwh_month, buy_c, sell_c, *, saved=True):
    if kwh_month is None or buy_c is None:
        return None
    rate = buy_c - (sell_c or 0.0) if saved else buy_c
    return round(kwh_month * rate / 100, 2)


def _effect(kwh_month, money, note):
    return {"kwh_month": None if kwh_month is None else round(kwh_month, 1),
            "money_month": money, "estimate": True, "note": note}


def suggest(current: dict, site: dict | None, objectives) -> list[dict]:
    """What to change for the chosen objectives, each with its action, numbers, why and an
    estimated effect a month. Never applied here: the host opens the right page with it."""
    objectives = list(objectives or [])
    bad = [o for o in objectives if o not in OBJECTIVES]
    if bad:
        raise ValueError(f"unknown objective(s): {', '.join(bad)}")
    want = set(objectives)
    site = site or {}
    tariff = site.get("tariff") or {}
    buy, sell = _num(tariff.get("buy_c")), _num(tariff.get("sell_c"))
    cap, reserve = _num(site.get("capacity_kwh")), _num(site.get("reserve_pct"))
    mode, days = site.get("mode"), _days(current)
    r = ratios(current, cap)
    imp, exp = _num(current.get("grid_import")), _num(current.get("grid_export"))
    per_day = (lambda v: v / days) if days else (lambda v: None)
    out = []

    # Emergency Backup holding a full battery: its energy could replace imports.
    if (mode == "backup" and want & {"self_sufficiency", "lowest_bill"}
            and r["cycles_per_day"] is not None and r["cycles_per_day"] < 0.2
            and cap and imp and days):
        keep = max(reserve or 0, _MIN_RESERVE)
        usable = cap * (1 - keep / 100) * 0.9
        shift = min(usable, per_day(imp)) * _DAYS_PER_MONTH
        out.append({
            "id": "backup_to_self", "kind": "suggestion",
            "objectives": sorted(want & {"self_sufficiency", "lowest_bill"}),
            "headline": f"Self-Consumption with a {keep:.0f}% reserve",
            "numbers": {"cycles_per_day": r["cycles_per_day"], "grid_import_per_day":
                        per_day(imp), "usable_kwh": usable},
            "why": (f"In Emergency Backup the battery did {r['cycles_per_day']:.2f} cycles a "
                    f"day while {per_day(imp):.1f} kWh a day came from the grid. "
                    f"Self-Consumption uses the battery above a {keep:.0f}% reserve, which "
                    "stays for an outage."),
            "action": {"type": "mode", "mode": "self", "reserve_pct": int(keep)},
            "effect": _effect(shift, _money(shift, buy, sell, saved=False),
                              "Up to this much less from the grid, if the battery fills from "
                              "solar each day."),
        })

    # A TOU tariff run in Self-Consumption: the battery may be empty by the peak.
    if (mode == "self" and "lowest_bill" in want and tariff.get("kind") == "tou"
            and tariff.get("peak")):
        out.append({
            "id": "self_to_tou", "kind": "suggestion", "objectives": ["lowest_bill"],
            "headline": "Time-of-Use, holding the battery for the peak "
                        f"({', '.join(tariff['peak'])})",
            "numbers": {"buy_c": buy, "sell_c": sell, "peak": tariff["peak"]},
            "why": ("On a time-of-use tariff, Self-Consumption can use the battery up before "
                    "the peak, so peak hours are bought at the highest price. Time-of-Use (or a "
                    "schedule for the peak) keeps it for then."),
            "action": {"type": "mode", "mode": "tou", "template": "tou_if_charged"},
            "effect": _effect(None, None, "Sized from the Day view: how much was imported "
                                          "in the peak."),
        })

    # A high reserve leaves most of the battery unused for everyday saving.
    if (want & {"self_sufficiency", "lowest_bill"} and mode != "backup" and reserve is not None
            and reserve >= 50 and cap and imp and days):
        freed = cap * (reserve - _MIN_RESERVE) / 100
        shift = min(freed, per_day(imp)) * _DAYS_PER_MONTH
        out.append({
            "id": "lower_reserve", "kind": "suggestion",
            "objectives": sorted(want & {"self_sufficiency", "lowest_bill"}),
            "headline": f"Reserve {_MIN_RESERVE}% instead of {reserve:.0f}%",
            "numbers": {"reserve_pct": reserve, "freed_kwh": freed},
            "why": (f"A {reserve:.0f}% reserve keeps {cap * reserve / 100:.1f} kWh idle every "
                    f"day while {per_day(imp):.1f} kWh a day came from the grid."),
            "action": {"type": "reserve", "reserve_pct": _MIN_RESERVE},
            "effect": _effect(shift, _money(shift, buy, sell, saved=False),
                              "Up to this much less from the grid; less is kept for an outage."),
        })

    # Backup ready: keep enough for an outage.
    if "backup_ready" in want and reserve is not None and reserve < _BACKUP_RESERVE:
        cost = cap * (_BACKUP_RESERVE - reserve) / 100 * _DAYS_PER_MONTH if cap else None
        out.append({
            "id": "raise_reserve", "kind": "suggestion", "objectives": ["backup_ready"],
            "headline": f"Reserve {_BACKUP_RESERVE}% instead of {reserve:.0f}%",
            "numbers": {"reserve_pct": reserve, "capacity_kwh": cap},
            "why": (f"At {reserve:.0f}% an outage at the end of the day finds the battery "
                    "almost empty."),
            "action": {"type": "reserve", "reserve_pct": _BACKUP_RESERVE},
            "effect": _effect(-cost if cost is not None else None,
                              -_money(cost, buy, sell, saved=False)
                              if _money(cost, buy, sell, saved=False) is not None else None,
                              "At most this much more from the grid a month."),
        })

    # Battery care: heavy cycling wears the battery.
    if ("battery_care" in want and r["cycles_per_day"] is not None
            and r["cycles_per_day"] > 1.0):
        out.append({
            "id": "heavy_cycling", "kind": "suggestion", "objectives": ["battery_care"],
            "headline": f"The battery cycles {r['cycles_per_day']:.1f} times a day",
            "numbers": {"cycles_per_day": r["cycles_per_day"]},
            "why": ("More than one full cycle a day usually means charging from the grid and "
                    "discharging again; check schedules that force charge or export."),
            "action": {"type": "schedules"},
            "effect": _effect(None, None, "Fewer cycles, at the cost of what those cycles "
                                          "earned."),
        })

    # Export earnings: sell the battery's energy when export pays most.
    if ("export_earnings" in want and cap and tariff.get("kind") in ("tou", "dynamic")
            and r["solar_used"] is not None):
        out.append({
            "id": "export_window", "kind": "suggestion", "objectives": ["export_earnings"],
            "headline": "Export from the battery in the best-paid window",
            "numbers": {"sell_c": sell, "solar_used": r["solar_used"]},
            "why": ("With a time-of-use or wholesale feed-in, the same kWh earns more in the "
                    "evening peak or a price spike than at midday."),
            "action": {"type": "schedule", "template": "export_bonus"},
            "effect": _effect(None, None, "Depends on the window's price; the Day view shows "
                                          "what was exported when."),
        })
    return out


def summarise(current: dict, *, previous: dict | None = None, last_year: dict | None = None,
              history: list[dict] | None = None, site: dict | None = None,
              objectives=()) -> dict:
    """The Explain answer in one: ratios, trends, findings and suggestions."""
    site = site or {}
    return {
        "ratios": ratios(current, site.get("capacity_kwh")),
        "trends": trends(current, previous=previous, last_year=last_year, history=history),
        "findings": findings(current, site),
        "suggestions": suggest(current, site, objectives),
        "objectives": [{"id": o, "label": OBJECTIVES[o]} for o in objectives],
    }
