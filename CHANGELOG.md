# Changelog

## [Unreleased]

## [0.1.2] — 2026-11-09

### Added
- **Today** next to the date stepping: back to the period that holds today (on the host's
  site calendar). Off while today's period is showing. The payload says so in `current`.
- **Series chips:** the legend is a row of chips; tap one to hide or show that series. The
  chart rescales to what is shown. Remembered in `fwh-cloud-analytics:hidden`.
- **Line | Area** for Day (5-min): Area fills each line down to zero, gaps stay gaps.
  Remembered in `fwh-cloud-analytics:area`.

### Changed
- Refresh sits at the end of the status line, and the Line | Area and Stacked switches at
  the end of the chips, so the period and date bar stays one line on a phone.
- The PyPI workflow is `.github/workflows/publish.yml` again, like the other shared
  packages.

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
