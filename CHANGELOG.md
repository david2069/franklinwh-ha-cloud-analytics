# Changelog

## [Unreleased]

## [0.1.23] — 2026-11-10

### Fixed
- **A range's axis**: in 5-minute and hourly ranges the date went before the time on one
  line and ran into the next label; it now sits on a second line under the time where the
  day changes, as the bridges' own axis does.

## [0.1.22] — 2026-11-10

### Fixed
- **Mounting on a custom range**: `mount(el, {period: "custom", range: {from, to}})` read a
  day instead of the range, since an unknown period fell back to Day (5-min).

## [0.1.21] — 2026-11-10

### Added
- **A custom From-To range**: `fetch_range(client, start, end, …)` joins and trims the day,
  month or year replies a range needs into one payload (`period: "custom"`): 5-minute power
  up to 2 days, hourly kWh up to 31 days, daily up to a year, monthly beyond. The panel's
  `setRange(from, to)` draws it, with the date on the axis where the day changes; the demo
  serves it. `build(…, dated_hours=True)` keeps the date in hourly labels.

## [0.1.20] — 2026-11-10

### Added
- **`showAt("HH:MM")`** opens the readout at the slot nearest that time on the Day views,
  again after each load until `showAt(null)`, for a host's own time picker.

## [0.1.19] — 2026-11-10

### Added
- **`socAxis: "always"`** keeps the SoC % axis on the right for the periods with no SoC
  (Week to Lifetime), so the plot is as wide as a host's own chart that always has it.

## [0.1.18] — 2026-11-10

### Added
- **`refreshControl: false`** drops the panel's ↻ (a host's own Refresh calls `reload()`),
  and **`statusBelow: true`** puts the status line under the chart, where a host's own note
  sits, so both charts start at the same height.

## [0.1.17] — 2026-11-10

### Fixed
- **Grid lines took the Grid series' colour:** 0.1.16 named their token `--ca-grid`, which
  is the Grid series' own colour. The grid lines' token is now `--ca-gridline`.

## [0.1.16] — 2026-11-10

### Changed
- **The chart looks like the bridges' own** (owner): the unit (kW, kWh) is a rotated title
  on the left; SoC has its own axis on the right in tens (twenties on a short chart),
  titled **SoC %**, in its colour, and its line is solid; labelled times get faint vertical
  grid lines. `--ca-grid` sets the grid lines' colour.
- **The Details menu scrolls** when its list is taller than the screen allows.

## [0.1.15] — 2026-11-10

### Fixed
- **The Details menu stays on screen:** on a phone it could open past the left edge; it now
  shifts to fit inside the window, whichever side of the row its button is on.

## [0.1.14] — 2026-11-10

### Added
- **`setPeriod(p, date)`:** a host that changes its span and day together reads once,
  rather than twice with the replies racing.

## [0.1.13] — 2026-11-10

### Added
- **Details ▾** (owner): the cloud's other fields are no longer a row of chips. A
  **Details ▾** button after the chips opens a checklist of those with data; only the
  ticked ones get a chip (remembered). It opens leftwards near the right edge.
- **Host-owned Stack and date:** `{stackControl: false, stacked}` with `setStacked()`, and
  `{navControl: false, date}` with `setDate()` / `date()`, so a host can put one Stack
  toggle and one date picker over its local and cloud views.

### Changed
- **Chips look like the bridges' own:** a round dot, tinted in the series colour when on,
  faded when off, no outline. `--ca-menu-bg` sets the Details menu's background.

## [0.1.12] — 2026-11-10

### Added
- **The period's flows for a Sankey:** the payload's `flows` gives kWh per arc
  (`solar_to_home`, `solar_to_battery`, `solar_to_grid`, `battery_to_home`,
  `battery_to_grid`, `grid_to_home`, `grid_to_battery`, and the generator's) over the whole
  period: the cloud's own breakdown for Week to Lifetime, the 5-minute flows × 5/60 h for a
  day; `null` when the reply has no breakdown. The JSON export includes it.

## [0.1.11] — 2026-11-10

### Added
- **Host-owned chart style:** `mount(el, {styleControl: false, style: "bars"})` draws no
  Line | Area | Bars of its own; the host calls `setStyle("line" | "area" | "bars" | null)`
  (null: lines for a day, bars otherwise) and remembers the choice itself. `style()` returns
  the style drawn.

## [0.1.10] — 2026-11-10

### Added
- **The cloud's other fields as chips** (#13): every other field with data for the shown
  period gets a chip that starts **off** and is remembered once switched on. kWh periods:
  home from solar, grid and battery; battery charged from solar and grid; export from solar
  and battery. Day views: each 5-minute flow (solar → home, grid → battery, …), in kW, or
  kWh per hour for Day (hourly). They take their source's colour, dashed or lighter, and stay
  out of stacked bars (they are parts of the balance). Fields empty for the period (V2L, the
  solar sub-meters) get no chip; the payload's new `raw` keeps every array the cloud
  returned, and the JSON export includes it.

## [0.1.9] — 2026-11-10

### Added
- **Chart height:** `mount(el, {height: 380})` draws the chart that many pixels tall at any
  width, so a host's local and cloud charts are the same size.

## [0.1.8] — 2026-11-10

(0.1.7 was tagged on the 0.1.6 commit by mistake and never reached PyPI.)

### Added
- **State of charge on the Day views:** Day (5-min) draws the cloud's SoC (`socArray`) and
  Day (hourly) its hourly mean, as a dashed line on a 0–100 % axis at the right, with a
  chip, the readout and the export, as Local and the FranklinWH app show it. Week to
  Lifetime have none (the cloud's totals carry no SoC).

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
