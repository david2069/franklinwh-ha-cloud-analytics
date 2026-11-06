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

Status: scaffold. Nothing is built yet; the phased plan is in
[direct-connect-bridge #215](https://github.com/david2069/franklinwh-direct-connect-bridge/issues/215).

## How a bridge will use it

The bridge keeps the cloud credentials, its routes and its database. This package makes
the cloud calls through [franklinwh-cloud](https://github.com/david2069/franklinwh-cloud),
builds one payload per period, and ships a dependency-free panel the bridge mounts under
its Analytics page.

## Licence

MIT
