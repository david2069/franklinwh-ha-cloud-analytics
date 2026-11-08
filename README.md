# franklinwh-ha-cloud-analytics

The FranklinWH cloud's energy reporting, shared by the FranklinWH bridges. It sits next to
a bridge's own (local) analytics behind a **Local / Cloud** switch: the same controls,
two different sources, and the page always says which one it is showing.

- **Periods:** Day (5-min), Day (hourly), Week, Month, Year, Lifetime, with a date picker.
- **Chart:** home load, solar, battery (discharge +, charge −) and grid (import +,
  export −) in the site's time zone.
- **Totals:** solar production (to home, battery, grid), battery flows (discharged by
  destination, charged by source), grid flows (imported / exported) and home load (by
  source), each value with how sure the source is of it.
- **History:** imported into the bridge's own database (closed months once, the current
  month refreshed) for monthly, annual and lifetime totals, queries and download.

Status: phase 1 (periods, chart payload, panel). The phased plan is in
[direct-connect-bridge #215](https://github.com/david2069/franklinwh-direct-connect-bridge/issues/215).

## How a bridge uses it

The bridge keeps the cloud credentials, its routes and its database. This package makes
the cloud calls through [franklinwh-cloud](https://github.com/david2069/franklinwh-cloud),
builds one payload per period, and ships a dependency-free panel the bridge mounts under
its Analytics page.

```python
import franklinwh_ha_cloud_analytics as ca

cache = ca.Cache()                       # one per bridge; keyed by gateway below

# GET /api/analytics/cloud?period=month&date=2026-11-05
payload = await ca.fetch(client, "month", date(2026, 11, 5), today=site_today,
                         cache=cache, key=gateway_id)
```

`client` is a logged-in franklinwh-cloud client for the gateway, and `site_today` is
today's date in the site's own time zone. Serve `ca.static_dir()` at `/cloud-analytics/`,
then:

```html
<link rel="stylesheet" href="cloud-analytics/cloud-analytics.css">
<script src="cloud-analytics/cloud-analytics.js"></script>
<script>FWHCloudAnalytics.mount(el, {endpoint: "api/analytics/cloud",
                                    params: () => ({gateway: currentGatewayId})});</script>
```

`python -m franklinwh_ha_cloud_analytics.demo` serves the panel over made-up data.

## Periods

| Period | Library call | Chart |
|---|---|---|
| Day (5-min) | `get_power_by_day(day)` | lines, kW |
| Day (hourly) | `get_power_by_day(day)`, added up per hour | bars, kWh |
| Week | `get_power_details(2, its Monday)` | bars per day, kWh |
| Month | `get_power_details(3, the 1st)` | bars per day, kWh |
| Year | `get_power_details(4, 1 January)` | bars per month, kWh |
| Lifetime | `get_power_details(5, today)` | bars per year, kWh |

A Day request to `get_power_details` returns a single bucket, so both Day views read the
5-minute power. There, home, battery and grid are sums of the cloud's directional flows
(solar → home, grid → battery, …), so they're marked derived (≈). Every series carries
the weakest evidence rating of the fields it uses (franklinwh-cloud's field dictionary);
INFERRED ones are labelled. No data stays null, never 0. Signs: battery discharge +,
charge −; grid import +, export −.

Caching: a period that today falls in is kept for 5 minutes, a finished one for 6 hours.
The cloud's rate limit is per account, shared with the FranklinWH app.

## Licence

MIT
