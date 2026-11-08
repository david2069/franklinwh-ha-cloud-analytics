# Changelog

## [0.1.0] — 2026-11-09

### Added
- Phase 1 (direct-connect-bridge #215): `resolve()` periods (Day 5-min, Day hourly, Week,
  Month, Year, Lifetime) with the site calendar's previous and next period; `build()` chart
  payload with signs, nulls and evidence ratings; `fetch()` making the one franklinwh-cloud
  call a period needs, with `Cache`; and the `FWHCloudAnalytics.mount()` panel (period
  picker, date stepping, chart, legend). `demo` serves it over made-up data.
