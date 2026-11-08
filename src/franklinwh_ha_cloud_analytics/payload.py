"""The chart payload: the library's arrays as series, in the bridges' signs.

kWh periods (Week, Month, Year, Lifetime) plot the cloud's own totals as bars. Day (5-min)
plots lines in kW, and Day (hourly) bars in kWh, both made from the 5-minute directional
flows, so those series are marked derived. Each series carries the weakest evidence rating
of the fields it uses (franklinwh_cloud.const.energy_fields). Signs: battery discharge +,
charge −; grid import +, export −. No data stays null, never 0.
"""
from __future__ import annotations

from franklinwh_cloud.const.energy_fields import ELECTRIC_FIELDS, POWER_FIELDS

from .periods import Period

_EVIDENCE = {f.api: f.evidence for f in (*ELECTRIC_FIELDS, *POWER_FIELDS)}
_RANK = {"CONFIRMED": 0, "CORROBORATED": 1, "INFERRED": 2}
SAMPLES_PER_HOUR = 12

LABELS = {"home": "Home load", "solar": "Solar", "generator": "Generator",
          "battery": "Battery", "battery_discharge": "Battery discharged",
          "battery_charge": "Battery charged", "grid": "Grid",
          "grid_import": "Grid imported", "grid_export": "Grid exported"}

#: kWh totals per bucket (getFhpElectricData): key → (API array, sign).
_TOTALS = (("home", "kwhLoadArray", 1), ("solar", "kwhSuArray", 1),
           ("generator", "kwhGenArray", 1), ("battery_discharge", "kwhFhpDiArray", 1),
           ("battery_charge", "kwhFhpChgArray", -1), ("grid_import", "kwhUtiInArray", 1),
           ("grid_export", "kwhUtiOutArray", -1))

# The 5-minute directional flows (getFhpPowerByDay; "Gird" is the API's spelling).
_S_HOME, _S_GRID, _S_BAT = "powerSolarHomeArray", "powerSolarGirdArray", "powerSolarFhpArray"
_G_HOME, _G_BAT = "powerGirdHomeArray", "powerGirdFhpArray"
_B_HOME, _B_GRID = "powerFhpHomeArray", "powerFhpGirdArray"
_GEN_HOME, _GEN_BAT = "powerGenHomeArray", "powerGenFhpArray"

#: key → [(flow, sign)]: what each series adds up from the flows.
_LINES = {
    "home": [(_S_HOME, 1), (_G_HOME, 1), (_B_HOME, 1), (_GEN_HOME, 1)],
    "solar": [(_S_HOME, 1), (_S_GRID, 1), (_S_BAT, 1)],
    "battery": [(_B_HOME, 1), (_B_GRID, 1), (_S_BAT, -1), (_G_BAT, -1), (_GEN_BAT, -1)],
    "grid": [(_G_HOME, 1), (_G_BAT, 1), (_S_GRID, -1), (_B_GRID, -1)],
}
_HOURLY = {
    "home": _LINES["home"], "solar": _LINES["solar"],
    "generator": [(_GEN_HOME, 1), (_GEN_BAT, 1)],
    "battery_discharge": [(_B_HOME, 1), (_B_GRID, 1)],
    "battery_charge": [(_S_BAT, -1), (_G_BAT, -1), (_GEN_BAT, -1)],
    "grid_import": [(_G_HOME, 1), (_G_BAT, 1)],
    "grid_export": [(_S_GRID, -1), (_B_GRID, -1)],
}


def _weakest(apis) -> str:
    levels = [_EVIDENCE.get(a, "INFERRED") for a in apis]
    return max(levels, key=_RANK.__getitem__) if levels else "INFERRED"


def _series(key, values, apis, derived) -> dict:
    return {"key": key, "label": LABELS[key], "values": values,
            "evidence": _weakest(apis), "derived": derived}


def _combine(result: dict, parts, i: int):
    """One sample of a derived series. Flows the reply doesn't carry at all are left out
    (no generator on this site); a null in a flow it does carry makes the sample null."""
    total, seen = 0.0, False
    for api, sign in parts:
        arr = result.get(api)
        if not isinstance(arr, list):
            continue
        v = arr[i] if i < len(arr) else None
        if v is None:
            return None
        total += sign * v
        seen = True
    return round(total, 4) if seen else None


def _present(result: dict, parts) -> list[str]:
    return [a for a, _ in parts if isinstance(result.get(a), list)]


def build(period: Period, result: dict | None) -> dict:
    """The payload the panel draws for ``period`` from the library's reply ``result``."""
    result = result or {}
    labels = list(result.get("deviceTimeArray") or [])
    out = {"source": "cloud", "period": period.name, "date": period.start.isoformat(),
           "nav": {"prev": period.prev and period.prev.isoformat(),
                   "next": period.next and period.next.isoformat()},
           "current": period.current,
           "note": None}
    if period.name == "day5":
        series = [_series(k, [_combine(result, parts, i) for i in range(len(labels))],
                          _present(result, parts), True) for k, parts in _LINES.items()]
        out.update(chart="line", unit="kW")
    elif period.name == "dayhour":
        hours = [f"{h:02d}:00" for h in range(24)]
        idx: dict[str, list[int]] = {h: [] for h in hours}
        for i, t in enumerate(labels):
            hh = str(t).split(" ")[-1][:2] + ":00"
            if hh in idx:
                idx[hh].append(i)
        series = []
        for k, parts in _HOURLY.items():
            vals = []
            for h in hours:
                samples = [_combine(result, parts, i) for i in idx[h]]
                vals.append(None if not samples or None in samples
                            else round(sum(samples) / SAMPLES_PER_HOUR, 4))
            series.append(_series(k, vals, _present(result, parts), True))
        labels = hours if labels else []
        out.update(chart="bars", unit="kWh",
                   note="Hourly kWh added up from the 5-minute power, within about 3% of "
                        "the day's own totals.")
    else:
        series = []
        for k, api, sign in _TOTALS:
            arr = list(result.get(api) or [None] * len(labels))
            series.append(_series(k, [None if v is None else sign * v for v in arr],
                                  [api], False))
        out.update(chart="bars", unit="kWh")
    out["labels"] = labels
    out["series"] = series
    out["empty"] = not any(v is not None for s in series for v in s["values"])
    return out
