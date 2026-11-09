"""A local page with the panel over made-up data, for trying it and for the browser tests.

    python -m franklinwh_ha_cloud_analytics.demo [port]

No cloud call is made: the endpoint builds payloads from the shapes the library returns.
"""
from __future__ import annotations

import asyncio
import json
import math
import sys
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import build, fetch_range, resolve, static_dir

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cloud analytics demo</title><link rel="stylesheet" href="cloud-analytics/cloud-analytics.css">
<style>body{font-family:system-ui,sans-serif;margin:16px;background:#fff;color:#18202b}
@media (prefers-color-scheme:dark){body{background:#121924;color:#e4e9f0}}</style></head>
<body><p><button type="button" onclick="ca.exportData('csv')">Export CSV</button>
<button type="button" onclick="ca.exportData('json')">JSON</button></p>
<div id="ca"></div><script src="cloud-analytics/cloud-analytics.js"></script>
<script>const ca = FWHCloudAnalytics.mount(document.getElementById("ca"), {endpoint: "api/cloud"});</script>
</body></html>"""


def _day(on: date) -> dict:
    """288 five-minute samples of a sunny day: solar by day, battery at night."""
    t, flows = [], {k: [] for k in ("powerSolarHomeArray", "powerSolarGirdArray",
                                    "powerSolarFhpArray", "powerGirdHomeArray",
                                    "powerGirdFhpArray", "powerFhpHomeArray",
                                    "powerFhpGirdArray")}
    soc, socs = 40.0, []
    for i in range(288):
        h = i / 12
        t.append(f"{on.isoformat()} {int(h):02d}:{i % 12 * 5:02d}")
        sun = max(0.0, math.sin((h - 6) / 13 * math.pi)) * 6
        home = 0.6 + 0.8 * math.exp(-((h - 19) ** 2) / 4)
        s_home = min(sun, home)
        s_bat = min(sun - s_home, 3.0)
        b_home = home - s_home if sun < 0.2 else 0.0
        vals = {"powerSolarHomeArray": s_home, "powerSolarGirdArray": sun - s_home - s_bat,
                "powerSolarFhpArray": s_bat, "powerGirdHomeArray": home - s_home - b_home,
                "powerGirdFhpArray": 0.0, "powerFhpHomeArray": b_home, "powerFhpGirdArray": 0.0}
        for k, v in vals.items():
            flows[k].append(round(max(0.0, v), 3))
        soc = min(100.0, max(5.0, soc + (s_bat - b_home) / 12 / 13.6 * 100))
        socs.append(round(soc, 1))
    return {"deviceTimeArray": t, **flows, "socArray": socs}


def _buckets(labels: list[str], today: date) -> dict:
    out = {k: [] for k in ("kwhLoadArray", "kwhSuArray", "kwhGenArray", "kwhFhpDiArray",
                           "kwhFhpChgArray", "kwhUtiInArray", "kwhUtiOutArray")}
    for i, lab in enumerate(labels):
        future = lab > today.isoformat()[:len(lab)]
        base = 18 + 6 * math.sin(i)
        for k, v in zip(out, (base, base * 1.4, 0.0, base * 0.4, base * 0.45, 2.0, base * 0.5)):
            out[k].append(None if future else round(v, 2))
    return {"deviceTimeArray": labels, **out}


def payload(period: str, on: date, today: date) -> dict:
    p = resolve(period, on, today)
    if p.type is None:
        return build(p, _day(p.start) if p.start <= today else {})
    if period == "week":
        labels = [(p.start + timedelta(days=i)).isoformat() for i in range(7)]
    elif period == "month":
        nxt = date(p.start.year + p.start.month // 12, p.start.month % 12 + 1, 1)
        labels = [(p.start + timedelta(days=i)).isoformat() for i in range((nxt - p.start).days)]
    elif period == "year":
        labels = [f"{p.start.year}-{m:02d}" for m in range(1, 13)]
    else:
        labels = [str(y) for y in range(today.year - 3, today.year + 1)]
    return build(p, _buckets(labels, today))


class _Client:
    """The library's two calls over the made-up data, for a custom range."""
    def __init__(self, today: date):
        self.today = today

    async def get_power_by_day(self, day: str) -> dict:
        on = date.fromisoformat(day)
        return _day(on) if on <= self.today else {}

    async def get_power_details(self, type: int, on: str) -> dict:
        d = date.fromisoformat(on)
        if type == 3:
            nxt = date(d.year + d.month // 12, d.month % 12 + 1, 1)
            labels = [(d + timedelta(days=i)).isoformat() for i in range((nxt - d).days)]
        else:
            labels = [f"{d.year}-{m:02d}" for m in range(1, 13)]
        return _buckets(labels, self.today)


def custom(start: str, end: str, today: date) -> dict:
    return asyncio.run(fetch_range(_Client(today), datetime.fromisoformat(start),
                                   datetime.fromisoformat(end), today=today))


class Handler(BaseHTTPRequestHandler):
    today = date.today()

    def log_message(self, *a):  # quiet
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/api/cloud":
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if q.get("period") == "custom":
                    body = custom(q.get("from", ""), q.get("to", ""), self.today)
                else:
                    body = payload(q.get("period", "day5"),
                                   date.fromisoformat(q.get("date") or self.today.isoformat()),
                                   self.today)
                return self._send(json.dumps(body).encode(), "application/json")
            except ValueError as e:
                return self._send(json.dumps({"error": str(e)}).encode(), "application/json", 400)
        if u.path.startswith("/cloud-analytics/"):
            f = static_dir() / u.path.rsplit("/", 1)[-1]
            if f.is_file():
                ctype = "text/css" if f.suffix == ".css" else "text/javascript"
                return self._send(f.read_bytes(), ctype)
        self._send(b"not found", "text/plain", 404)


def serve(port: int = 8765, today: date | None = None) -> ThreadingHTTPServer:
    if today:
        Handler.today = today
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


if __name__ == "__main__":
    srv = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print(f"http://127.0.0.1:{srv.server_address[1]}/")
    srv.serve_forever()
