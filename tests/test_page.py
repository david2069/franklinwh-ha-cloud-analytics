"""The panel in a real browser: periods, stepping, units, nulls, empty periods.

Needs Playwright with a Chrome or Chromium; skipped where it isn't installed.
"""
import threading
from datetime import date

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

from franklinwh_ha_cloud_analytics.demo import serve  # noqa: E402

TODAY = date(2026, 11, 9)


@pytest.fixture(scope="module")
def base():
    srv = serve(port=0, today=TODAY)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome", headless=True)
        except Exception:  # noqa: BLE001
            try:
                b = p.chromium.launch(headless=True)
            except Exception as e:  # noqa: BLE001
                pytest.skip(f"no browser: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser, base):
    ctx = browser.new_context(viewport={"width": 1100, "height": 800})
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    # a fresh start once per test; a reload inside the test keeps what was remembered
    pg.add_init_script("if (!sessionStorage.t) { localStorage.clear(); sessionStorage.t = 1; }")
    pg.goto(base + "/")
    pg.wait_for_selector(".fwhca-chart svg")
    yield pg
    assert errors == []
    ctx.close()


def _status(pg):
    return pg.locator(".fwhca-status").inner_text()


def test_opens_on_day_5min_lines_in_kw(page):
    assert page.input_value(".fwhca-period") == "day5"
    assert page.locator(".fwhca-line").count() >= 3
    assert page.locator("svg text").first.text_content() == "kW"
    assert "Showing cloud data from the FranklinWH cloud" in _status(page)


def test_periods_switch_to_kwh_bars_and_remember(page):
    page.select_option(".fwhca-period", "month")
    page.wait_for_selector(".fwhca-bar-r")
    assert page.locator("svg text").first.text_content() == "kWh"
    assert page.input_value("input[type=date]") == "2026-11-01"
    assert page.locator("[data-step=next]").is_disabled()          # no future month
    page.click("[data-step=prev]")
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-10-01'")
    page.reload()
    page.wait_for_selector(".fwhca-bar-r")
    assert page.input_value(".fwhca-period") == "month"


def test_week_snaps_to_monday_and_lifetime_has_no_dates(page):
    page.select_option(".fwhca-period", "week")
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-11-09'")
    page.fill("input[type=date]", "2026-11-05")
    page.dispatch_event("input[type=date]", "change")
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-11-02'")
    page.select_option(".fwhca-period", "lifetime")
    page.wait_for_selector(".fwhca-bar-r")
    assert page.locator(".fwhca-nav").is_hidden()


def test_hourly_says_it_is_derived_and_future_day_is_empty(page):
    page.select_option(".fwhca-period", "dayhour")
    page.wait_for_selector(".fwhca-bar-r")
    assert "5-minute" in page.locator(".fwhca-note").inner_text()
    assert "≈" in page.locator(".fwhca-legend").inner_text()
    page.fill("input[type=date]", "2026-12-01")
    page.dispatch_event("input[type=date]", "change")
    page.wait_for_selector(".fwhca-empty")


def test_a_generator_that_never_ran_is_not_in_the_legend(page):
    page.select_option(".fwhca-period", "year")
    page.wait_for_selector(".fwhca-bar-r")
    assert "Generator" not in page.locator(".fwhca-legend").inner_text()
    assert page.locator(".fwhca-bar-r.c-generator").count() == 0


def test_phone_width_has_no_horizontal_scroll(browser, base):
    ctx = browser.new_context(viewport={"width": 375, "height": 740})
    pg = ctx.new_page()
    pg.goto(base + "/")
    pg.wait_for_selector(".fwhca-chart svg")
    assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    ctx.close()


def test_period_is_one_dropdown_so_the_bar_is_one_line_on_a_phone(browser, base):
    ctx = browser.new_context(viewport={"width": 375, "height": 740})
    pg = ctx.new_page()
    pg.goto(base + "/")
    pg.wait_for_selector(".fwhca-chart svg")
    assert pg.locator("select.fwhca-period option").count() == 6
    period, nav = pg.locator(".fwhca-period").bounding_box(), pg.locator(".fwhca-nav").bounding_box()
    assert abs(period["y"] - nav["y"]) < 4          # side by side, not stacked
    ctx.close()


def test_bars_can_be_stacked_and_the_choice_is_remembered(page):
    page.select_option(".fwhca-period", "week")
    page.wait_for_selector(".fwhca-bar-r")
    page.click("[data-step=prev]")                       # a whole week of data
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-11-02'")
    page.wait_for_selector(".fwhca-bar-r")
    btn = page.locator("[data-stack]")
    assert btn.is_visible() and btn.get_attribute("aria-pressed") == "false"
    xs = lambda: {round(float(r.get_attribute("x"))) for r in page.locator(".fwhca-bar-r").all()}
    side_by_side = len(xs())
    btn.click()
    assert btn.get_attribute("aria-pressed") == "true"
    assert len(xs()) == 7 < side_by_side                 # one column per day
    assert "came from above zero" in page.locator(".fwhca-note").inner_text()
    zero = page.evaluate("+document.querySelector('.fwhca-grid.zero').getAttribute('y1')")
    home = page.locator(".fwhca-bar-r.c-home").first
    assert float(home.get_attribute("y")) >= zero - 0.5   # home load is a use: below zero
    hb = home.bounding_box()
    page.mouse.move(hb["x"] + hb["width"] / 2, hb["y"] + hb["height"] / 2)
    assert "Home load: -" not in page.locator(".fwhca-tip").inner_text()   # the real value
    page.reload()
    page.wait_for_selector(".fwhca-bar-r")
    assert page.locator("[data-stack]").get_attribute("aria-pressed") == "true"
    assert len(xs()) == 1                                # this week: today only, one column
    page.select_option(".fwhca-period", "day5")
    page.wait_for_selector(".fwhca-line")
    assert page.locator("[data-stack]").is_hidden()     # lines don't stack


def test_today_jumps_back_to_the_current_period(page):
    # Owner, 2026-11-09: a quick Today button.
    today = page.locator("[data-today]")
    assert today.is_disabled()                           # already on today
    page.select_option(".fwhca-period", "month")
    page.wait_for_selector(".fwhca-bar-r")
    page.click("[data-step=prev]")
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-10-01' && !document.querySelector('.fwhca-status').textContent.includes('Loading')")
    assert not today.is_disabled()
    today.click()
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-11-01' && !document.querySelector('.fwhca-status').textContent.includes('Loading')")
    assert today.is_disabled()


def test_series_chips_show_and_hide_and_are_remembered(page):
    # Owner, 2026-11-09: the same metric filter chips as the bridge's Local view.
    chip = page.locator(".fwhca-key[data-key=solar]")
    assert chip.get_attribute("aria-pressed") == "true"
    assert page.locator(".fwhca-line.c-solar").count() == 1
    chip.click()
    assert chip.get_attribute("aria-pressed") == "false"
    assert page.locator(".fwhca-line.c-solar").count() == 0
    page.reload()
    page.wait_for_selector(".fwhca-chart svg")
    assert page.locator(".fwhca-key[data-key=solar]").get_attribute("aria-pressed") == "false"
    assert page.locator(".fwhca-line.c-solar").count() == 0


def test_every_period_can_be_bars_line_or_area_and_the_choice_is_remembered(page):
    # Owner, 2026-11-09: switch back to line and area from the bar charts.
    line, area, bars = (page.locator(f"[data-style={k}]") for k in ("line", "area", "bars"))
    assert line.get_attribute("aria-pressed") == "true"            # day: lines by default
    area.click()
    assert page.locator(".fwhca-area").count() >= 3
    page.select_option(".fwhca-period", "month")
    page.wait_for_selector(".fwhca-chart svg")
    assert page.locator(".fwhca-area").count() >= 3                 # the choice carries over
    bars.click()
    assert page.locator(".fwhca-bar-r").count() > 0 and page.locator(".fwhca-line").count() == 0
    line.click()
    assert page.locator(".fwhca-line").count() >= 3 and page.locator(".fwhca-bar-r").count() == 0
    assert page.locator("[data-stack]").is_hidden()                 # stacking is for bars
    page.reload()
    page.wait_for_selector(".fwhca-line")
    assert page.locator("[data-style=line]").get_attribute("aria-pressed") == "true"


def test_tapping_the_chart_shows_every_value_at_that_time(page):
    # Owner, 2026-11-09: like Local, the breakdown at the point tapped or hovered.
    box = page.locator(".fwhca-chart svg").bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    tip = page.locator(".fwhca-tip")
    tip.wait_for(state="visible")
    text = tip.inner_text()
    assert "Home load" in text and "Solar" in text and "kW" in text
    assert page.locator(".fwhca-guide").count() == 1
    page.click(".fwhca-key[data-key=solar]")                        # hidden series leave the readout
    page.mouse.move(box["x"] + box["width"] / 2 + 3, box["y"] + box["height"] / 2)
    assert "Solar" not in tip.inner_text()


@pytest.mark.parametrize("locale,axis,status", [("en-AU", "1 Nov", "1 Nov 2026"), ("en-US", "Nov 1", "Nov 1, 2026")])
def test_dates_follow_the_browsers_own_format(browser, base, locale, axis, status):
    # Owner, 2026-11-09: no US mm-dd on an AU browser; dates come from the browser's locale.
    ctx = browser.new_context(locale=locale, viewport={"width": 1100, "height": 800})
    pg = ctx.new_page()
    pg.goto(base + "/")
    pg.wait_for_selector(".fwhca-chart svg")
    pg.select_option(".fwhca-period", "month")
    pg.wait_for_function("document.querySelector('.fwhca-status').textContent.includes('read') || document.querySelector('.fwhca-status').textContent.includes('cloud')")
    pg.wait_for_selector(".fwhca-bar-r")
    ticks = pg.locator("svg text.fwhca-ax").all_text_contents()
    assert axis in ticks and not any(t.startswith("11-") for t in ticks)
    assert status in pg.locator(".fwhca-status").inner_text()
    ctx.close()


def test_exports_the_shown_period_as_csv_and_json(page, tmp_path):
    # Owner, 2026-11-09: CSV and JSON export like the bridge's Local view.
    page.select_option(".fwhca-period", "month")
    page.wait_for_function("document.querySelector('input[type=date]').value === '2026-11-01' && !document.querySelector('.fwhca-status').textContent.includes('Loading')")
    with page.expect_download() as dl:
        page.click("text=Export CSV")
    d = dl.value
    assert d.suggested_filename == "fwh-cloud-month-2026-11-01.csv"
    rows = open(d.path(), encoding="utf-8").read().splitlines()
    assert rows[0].startswith("date,Home load (kWh),Solar (kWh)")
    assert rows[1].startswith("2026-11-01,") and len(rows) == 31        # header + every day
    page.click(".fwhca-key[data-key=solar]")                             # hidden on the chart, still exported
    with page.expect_download() as dl:
        page.click("text=JSON")
    import json
    body = json.load(open(dl.value.path(), encoding="utf-8"))
    assert dl.value.suggested_filename == "fwh-cloud-month-2026-11-01.json"
    assert body["period"] == "month" and body["unit"] == "kWh" and "solar" in [s["key"] for s in body["series"]]
