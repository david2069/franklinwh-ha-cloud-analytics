# Changelog

## [Unreleased]

## [0.1.6] — 2026-11-09

### Added
- **Host-owned period picker:** `mount(el, {periodPicker: false, period: "week"})` draws no
  picker of its own; the host calls `setPeriod()` from its own (one picker for a bridge's
  local and cloud views) and remembers the period itself. `period()` returns the shown one
  and `FWHCloudAnalytics.PERIODS` lists them.

## [0.1.5] — 2026-11-09

### Added
- **CSV and JSON export:** `mount()` returns `exportData("csv" | "json")`, which downloads
  the shown period as `fwh-cloud-<period>-<date>.csv` / `.json`: every series the cloud
  returned (a chip only hides one on the chart), labels as the cloud gave them, a missing
  value left empty (`null` in JSON). The host places the buttons, next to its own export.

## [0.1.4] — 2026-11-09

### Fixed
- **Dates follow the browser's own format.** The axis showed ISO slices (`11-05`, read as
  month-day); it now shows `5 Nov` on an Australian browser and `Nov 5` on an American
  one, from the browser's locale. The status line and the readout's heading use it too
  (the readout with the weekday). Times stay 24-hour.

## [0.1.3] — 2026-11-09

### Added
- **Readout:** hover, or tap on a phone, anywhere on the chart for every shown series'
  value at that time, with a guide line, as the bridges' own Analytics does. It replaces
  the per-bar and per-column hover titles.
- **Line | Area | Bars** for every period (it replaces 0.1.2's Line | Area on Day only).
  Until one is picked, a day draws lines and the longer periods bars; the pick is
  remembered in `fwh-cloud-analytics:style`. Stacked is offered with Bars.

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
