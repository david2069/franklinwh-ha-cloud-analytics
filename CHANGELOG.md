# Changelog

## [0.1.1] — 2026-11-09

### Changed
- The PyPI workflow is `.github/workflows/release.yaml`, matching the trusted publisher
  set up on PyPI. 0.1.0 was tagged but never reached PyPI; 0.1.1 is the same code.

## [0.1.0] — 2026-11-09

### Added
- Phase 1 (direct-connect-bridge #215): `resolve()` periods (Day 5-min, Day hourly, Week,
  Month, Year, Lifetime) with the site calendar's previous and next period; `build()` chart
  payload with signs, nulls and evidence ratings; `fetch()` making the one franklinwh-cloud
  call a period needs, with `Cache`; and the `FWHCloudAnalytics.mount()` panel (period
  dropdown, date stepping, chart, legend; one line on a phone; an optional **stacked** toggle
  for the bar charts (where the energy came from above zero, where it went below), remembered). `demo` serves it over made-up data.
