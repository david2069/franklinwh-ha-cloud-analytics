/* FranklinWH cloud analytics: the period picker and chart, drawn inside a host's page.
 *
 * The bridge serves this file and cloud-analytics.css at /cloud-analytics/, includes both,
 * and calls FWHCloudAnalytics.mount(el, {endpoint: "api/analytics/cloud"}). The endpoint
 * takes ?period=&date= (and anything the host adds through params(), such as its gateway)
 * and returns franklinwh_ha_cloud_analytics.build()'s payload, or {error: "..."}. Dates
 * and their steps come from the payload (the site's own calendar), never from this
 * browser's clock in UTC.
 *
 * A host with its own period picker (one picker for its local and cloud views) passes
 * {periodPicker: false, period: "week"} and calls setPeriod() from it; the panel then draws
 * no picker of its own and leaves remembering the period to the host. {height: 380} draws
 * the chart that many pixels tall at any width, to match the host's own chart. A host with its
 * own Line | Area | Bars passes {styleControl: false, style: "bars"} and calls setStyle()
 * (null = lines for a day, bars otherwise); style() is the one drawn. {stackControl: false,
 * stacked} with setStacked(), and {navControl: false, date} with setDate() / date(), hand
 * the Stack toggle and the date stepping to the host as well. {refreshControl: false} drops
 * the ↻ (the host's own Refresh calls reload()), and {statusBelow: true} puts the status line
 * under the chart. {socAxis: "always"} keeps the SoC % axis (and so the plot's width) for the
 * periods with no SoC. setRange("2026-11-05T22:00", "2026-11-06T02:00") shows a custom
 * From-To range (?period=custom&from=&to=, franklinwh_ha_cloud_analytics.fetch_range());
 * setPeriod() goes back to a period.
 */
(function () {
  "use strict";

  const PERIODS = [["day5", "Day (5-min)"], ["dayhour", "Day (hourly)"], ["week", "Week"],
                   ["month", "Month"], ["year", "Year"], ["lifetime", "Lifetime"]];
  const KEY = "fwh-cloud-analytics:period";
  const KEY_STACK = "fwh-cloud-analytics:stacked";   // "1": bars stacked, one column per bucket
  const KEY_STYLE = "fwh-cloud-analytics:style";       // "line" | "area" | "bars"; unset: lines for a day, bars otherwise
  const STYLES = ["line", "area", "bars"];
  const KEY_HIDDEN = "fwh-cloud-analytics:hidden";     // JSON list of series keys switched off
  const KEY_EXTRAS = "fwh-cloud-analytics:extras";     // JSON list of extra series switched on (they start off)
  const list = (k) => { try { const h = JSON.parse(store.get(k) || "[]"); return Array.isArray(h) ? h : []; } catch (e) { return []; } };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  // Today in this browser's own zone (not toISOString, which is UTC). Only the first load
  // uses it; after that the payload's date and nav are the site's calendar.
  const localToday = () => { const d = new Date(); const p = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()); };
  const fmt = (v, unit) => v == null ? "no data" : (unit === "%" || Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)) + " " + unit;

  function mount(el, options) {
    const o = Object.assign({ endpoint: "api/analytics/cloud", params: null, sourceLabel: "the FranklinWH cloud",
                              periodPicker: true, period: null, height: null, styleControl: true, style: null,
                              stackControl: true, stacked: false, navControl: true, date: null,
                              refreshControl: true, statusBelow: false, socAxis: "auto" }, options || {});
    const st = { period: o.period || store.get(KEY) || "day5", date: o.date || localToday(), data: null, busy: false,
                 range: o.period === "custom" && o.range ? o.range : null,
                 stacked: o.stackControl ? store.get(KEY_STACK) === "1" : !!o.stacked, detailsOpen: false,
                 style: o.styleControl ? (STYLES.includes(store.get(KEY_STYLE)) ? store.get(KEY_STYLE) : null)
                                       : (STYLES.includes(o.style) ? o.style : null),
                 hidden: list(KEY_HIDDEN), extras: list(KEY_EXTRAS) };
    if (!PERIODS.some((p) => p[0] === st.period) && !(st.period === "custom" && st.range)) st.period = "day5";
    el.classList.add("fwhca");
    // the status line (and ↻), above the chart, or under it where a host's own note sits
    const statusbar = '<div class="fwhca-statusbar' + (o.statusBelow ? " fwhca-below" : "") + '"><p class="fwhca-status" aria-live="polite"></p>' +
      (o.refreshControl ? '<button type="button" data-refresh aria-label="Refresh" title="Refresh">↻</button>' : "") + "</div>";
    el.innerHTML =
      '<div class="fwhca-bar">' + (o.periodPicker ? '<select class="fwhca-period" aria-label="Period">' +
      PERIODS.map((p) => '<option value="' + p[0] + '">' + p[1] + "</option>").join("") +
      "</select>" : "<span></span>") + '<div class="fwhca-nav"><button type="button" data-step="prev" aria-label="Previous period">‹</button>' +
      '<input type="date" aria-label="Date"><button type="button" data-step="next" aria-label="Next period">›</button>' +
      '<button type="button" data-today title="Back to today">Today</button>' +
      '</div></div>' +
      (o.statusBelow ? "" : statusbar) + '<div class="fwhca-plot"><div class="fwhca-chart"></div><div class="fwhca-tip" hidden></div></div>' +
      (o.statusBelow ? statusbar : "") +
      '<div class="fwhca-legendbar"><div class="fwhca-legend"></div><div class="fwhca-view">' +
      '<div class="fwhca-seg" role="group" aria-label="Chart style">' +
      '<button type="button" data-style="line" aria-pressed="false">Line</button>' +
      '<button type="button" data-style="area" aria-pressed="false" title="Fill each line down to zero">Area</button>' +
      '<button type="button" data-style="bars" aria-pressed="false">Bars</button></div>' +
      '<button type="button" data-stack aria-pressed="false" aria-label="Stacked bars" title="Stacked: where the energy came from above zero, where it went below">' +
      '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 2h4v5H3zM3 9h4v5H3zM9 5h4v3H9zM9 10h4v4H9z" fill="currentColor"/></svg></button>' +
      '</div></div><p class="fwhca-note"></p>';
    const $ = (s) => el.querySelector(s);
    const dateIn = $("input[type=date]");

    el.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || st.busy) return;
      if (b.dataset.step && st.data && st.data.nav[b.dataset.step]) { st.date = st.data.nav[b.dataset.step]; load(); }
      else if ("refresh" in b.dataset) load(true);
      else if ("today" in b.dataset) { st.date = null; load(); }     // the host's today, on the site's calendar
      else if (b.dataset.style) { st.style = b.dataset.style; store.set(KEY_STYLE, st.style); render(); }
      else if (b.dataset.key) {
        const k = b.dataset.key, extra = st.data && st.data.series.some((s) => s.key === k && s.extra);
        const f = extra ? "extras" : "hidden";
        st[f] = st[f].includes(k) ? st[f].filter((h) => h !== k) : st[f].concat(k);
        store.set(extra ? KEY_EXTRAS : KEY_HIDDEN, JSON.stringify(st[f])); render();
      }
      else if ("stack" in b.dataset) { st.stacked = !st.stacked; store.set(KEY_STACK, st.stacked ? "1" : "0"); render(); }
      else if ("details" in b.dataset) { st.detailsOpen = !st.detailsOpen; render(); }
    });
    const periodIn = $(".fwhca-period");
    if (periodIn) periodIn.addEventListener("change", () => { st.period = periodIn.value; store.set(KEY, st.period); load(); });
    // setPeriod(p, date): a host changing its span and day together reads once.
    function setPeriod(p, date) {
      if (!PERIODS.some((x) => x[0] === p) || (p === st.period && (!date || date === st.date))) return;
      st.period = p; st.range = null;
      if (date) st.date = date;
      if (o.periodPicker) store.set(KEY, p);
      load();
    }
    // A host's own Line | Area | Bars (styleControl: false); null is automatic. Not stored.
    function setStyle(s) { st.style = STYLES.includes(s) ? s : null; render(); }
    // A host's own Stack toggle (stackControl: false) and date picker (navControl: false).
    function setStacked(on) { st.stacked = !!on; render(); }
    function setDate(d) { st.date = d || null; load(); }
    // A host's custom range: site-local "YYYY-MM-DDTHH:MM", the end not included.
    function setRange(from, to) {
      if (!from || !to || (st.period === "custom" && st.range && st.range.from === from && st.range.to === to)) return;
      st.period = "custom"; st.range = { from, to };
      load();
    }
    // Details ▾: tick the cloud's other fields to give them a chip (they start off).
    el.addEventListener("change", (e) => {
      const k = e.target.dataset && e.target.dataset.extra;
      if (!k) return;
      st.extras = e.target.checked ? st.extras.concat(k) : st.extras.filter((x) => x !== k);
      store.set(KEY_EXTRAS, JSON.stringify(st.extras)); render();
    });
    document.addEventListener("click", (e) => {
      if (st.detailsOpen && !e.target.closest(".fwhca-details")) { st.detailsOpen = false; render(); }
    });
    dateIn.addEventListener("change", () => { if (dateIn.value) { st.date = dateIn.value; load(); } });

    async function load(refresh) {
      st.busy = true; render();
      const q = new URLSearchParams(Object.assign({ period: st.period },
        st.period === "custom" && st.range ? { from: st.range.from, to: st.range.to } : st.date ? { date: st.date } : {},
        refresh ? { refresh: "1" } : {}, typeof o.params === "function" ? o.params() : o.params || {}));
      try {
        const r = await fetch(o.endpoint + (o.endpoint.includes("?") ? "&" : "?") + q);
        const j = await r.json().catch(() => ({ error: "HTTP " + r.status }));
        st.data = r.ok && !j.error ? j : { error: j.error || j.detail || "HTTP " + r.status };
        if (!st.data.error) st.date = st.data.date;
      } catch (e) { st.data = { error: "Could not reach the bridge: " + e.message }; }
      st.busy = false; render(); applyAt();
    }

    function render() {
      const d = st.data;
      if (periodIn) { periodIn.value = st.period; periodIn.disabled = st.busy; }
      const life = st.period === "lifetime";
      $(".fwhca-nav").hidden = life || !o.navControl;
      dateIn.value = st.date || "";
      dateIn.max = localToday();
      $("[data-step=prev]").disabled = !d || !!d.error || !d.nav || !d.nav.prev;
      $("[data-step=next]").disabled = !d || !!d.error || !d.nav || !d.nav.next;
      $("[data-today]").disabled = !d || !!d.error || !!d.current;
      const sty = d && !d.error ? style(d) : null;
      $(".fwhca-seg").hidden = !sty || !o.styleControl;
      STYLES.forEach((k) => $("[data-style=" + k + "]").setAttribute("aria-pressed", String(sty === k)));
      const stackBtn = $("[data-stack]");
      stackBtn.hidden = sty !== "bars" || !o.stackControl;
      stackBtn.setAttribute("aria-pressed", String(st.stacked));
      const status = $(".fwhca-status");
      status.classList.toggle("fwhca-err", !!(d && d.error));
      if (st.busy) status.textContent = "Loading from " + o.sourceLabel + "…";
      else if (!d) status.textContent = "";
      else if (d.error) status.textContent = d.error;
      else status.textContent = "Showing cloud data from " + o.sourceLabel + (life ? "" : " · " + (d.period === "custom" ? rangeText(d) : dateText(d.date, FULL))) +
        (d.fetched_at ? " · read " + new Date(d.fetched_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
      const ok = d && !d.error && !st.busy;
      $(".fwhca-chart").innerHTML = ok ? (d.empty ? '<p class="fwhca-empty">No cloud data for this period.</p>' : chart(d)) : "";
      $(".fwhca-legend").innerHTML = ok && !d.empty ? legend(d) : "";
      const menu = $(".fwhca-menu");                     // keep the whole menu on screen
      if (menu) {
        const r = menu.getBoundingClientRect(), vw = document.documentElement.clientWidth;
        let shift = r.right > vw - 8 ? vw - 8 - r.right : 0;
        if (r.left + shift < 8) shift = 8 - r.left;
        menu.style.left = shift + "px";
      }
      hideTip();
      $(".fwhca-note").textContent = ok ? [d.note, st.stacked && sty === "bars" && !d.empty
        ? "Stacked: where the energy came from above zero (solar, battery, grid import), where it went below (home, battery charge, grid export)." : null]
        .filter(Boolean).join(" ") : "";
    }

    // Series with nothing but null or 0 (a site with no generator) are left out; the chips
    // list the rest, and the chart draws the ones not switched off.
    const present = (d) => d.series.filter((s) => s.values.some((v) => v != null && v !== 0));
    // The cloud's other fields (extra) start off and are switched on one by one.
    const isOn = (s) => (s.extra ? st.extras.includes(s.key) : !st.hidden.includes(s.key));
    const shown = (d) => present(d).filter(isOn);

    function legend(d) {
      // the main series, then the picked details; Details ▾ lists every detail with data
      const details = present(d).filter((s) => s.extra);
      return present(d).filter((s) => !s.extra || isOn(s)).map((s) => {
        const on = isOn(s);
        return '<button type="button" class="fwhca-key c-' + esc(s.key) + (s.extra ? " fwhca-x" : "") + '" data-key="' + esc(s.key) + '" aria-pressed="' + on + '" title="' + (on ? "Hide " : "Show ") + esc(s.label) + '">' +
          '<i class="c-' + esc(s.key) + '"></i>' + esc(s.label) +
          (s.evidence === "INFERRED" ? ' <abbr title="Inferred from the field name; never checked">(inferred)</abbr>' : "") +
          (s.derived ? ' <abbr title="Added up from the cloud\'s 5-minute flows">≈</abbr>' : "") + "</button>";
      }).join("") + (details.length ? '<span class="fwhca-details"><button type="button" class="fwhca-key fwhca-more" data-details aria-haspopup="true" aria-expanded="' +
        st.detailsOpen + '">Details ▾</button>' + (st.detailsOpen ? '<span class="fwhca-menu" role="group" aria-label="Detailed metrics">' +
        details.map((s) => '<label><input type="checkbox" data-extra="' + esc(s.key) + '"' + (isOn(s) ? " checked" : "") + '><i class="c-' + esc(s.key) + '"></i>' +
          esc(s.label) + "</label>").join("") + "</span>" : "") + "</span>" : "");
    }

    function chart(d) {
      // drawn at the panel's own width, so axis text stays readable on a phone. SoC (axis
      // "pct") is a line on its own 0-100 % axis at the right, whatever the style.
      // Stacked bars are the energy balance, so the extra fields (parts of it) stay out.
      const P = shown(d).filter((s) => s.axis === "pct"),
            S = shown(d).filter((s) => s.axis !== "pct" && !(s.extra && st.stacked && style(d) === "bars")),
            n = d.labels.length, W = Math.max(300, Math.round($(".fwhca-chart").clientWidth || 720)),
            H = o.height || (W < 520 ? 220 : 260), soc = P.length || o.socAxis === "always", L = 52, R = soc ? 52 : 8, T = 16,
            dated = d.period === "custom" && (d.res === "5min" || d.res === "hour"),   // a date line under the times
            B = dated ? 40 : 28;
      const sty = style(d), stack = st.stacked && sty === "bars";
      // Stacked is an energy balance: sources above zero, uses below. Home load is a use, so
      // it is drawn below (its tooltip keeps the real value).
      const drawn = (s, v) => (stack && s.key === "home" && v != null ? -v : v);
      // Stacked: positives pile up above zero and negatives below, so the range is the
      // per-bucket sums rather than the single values.
      const vals = stack ? d.labels.flatMap((_, i) => [
          S.reduce((a, s) => a + Math.max(0, drawn(s, s.values[i]) || 0), 0),
          S.reduce((a, s) => a + Math.min(0, drawn(s, s.values[i]) || 0), 0)])
        : S.flatMap((s) => s.values).filter((v) => v != null);
      let hi = Math.max(0, ...vals), lo = Math.min(0, ...vals);
      if (hi === lo) hi = lo + 1;
      const step = nice((hi - lo) / 4);
      hi = Math.ceil(hi / step) * step; lo = Math.floor(lo / step) * step;
      const y = (v) => T + (hi - v) / (hi - lo) * (H - T - B);
      const cw = (W - L - R) / Math.max(n, 1), x = (i) => L + cw * (i + 0.5);
      let g = "";
      for (let v = lo; v <= hi + step / 2; v += step) {
        g += '<line class="fwhca-grid' + (Math.abs(v) < step / 1e6 ? " zero" : "") + '" x1="' + L + '" x2="' + (W - R) + '" y1="' + y(v) + '" y2="' + y(v) + '"/>' +
             '<text class="fwhca-ax" x="' + (L - 6) + '" y="' + (y(v) + 4) + '" text-anchor="end">' + +v.toFixed(2) + "</text>";
      }
      const yp = (v) => T + (100 - v) / 100 * (H - T - B);
      // SoC: its own axis on the right in tens (twenties when short), titled, as the bridges draw it
      if (soc) {
        const ps = H - T - B >= 250 ? 10 : 20;
        for (let v = 0; v <= 100; v += ps) g += '<text class="fwhca-ax fwhca-pct" x="' + (W - R + 6) + '" y="' + (yp(v) + 4) + '">' + v + "</text>";
        g += '<text class="fwhca-ax fwhca-pct" transform="translate(' + (W - 8) + " " + ((T + H - B) / 2) + ') rotate(90)" text-anchor="middle">SoC %</text>';
      }
      const every = Math.ceil(n / (W < 520 ? 4 : 8));
      let lastDay = null;
      d.labels.forEach((t, i) => {
        if (i % every) return;
        // a custom range in 5-minute or hourly slots: the time, and under it the date where
        // the day changes (as the bridges' own axis)
        let text = esc(short(t, d)), y0 = H - 8;
        if (dated) {
          const day = String(t).slice(0, 10);
          y0 = H - 22;
          if (day !== lastDay) text = '<tspan x="' + x(i) + '">' + text + '</tspan><tspan x="' + x(i) + '" dy="14">' + esc(dateText(day, DAY)) + "</tspan>";
          lastDay = day;
        }
        g += '<line class="fwhca-grid fwhca-vgrid" x1="' + x(i) + '" x2="' + x(i) + '" y1="' + T + '" y2="' + (H - B) + '"/>' +
             '<text class="fwhca-ax" x="' + x(i) + '" y="' + y0 + '" text-anchor="middle">' + text + "</text>";
      });
      geo = { W, L, cw: (W - L - R) / Math.max(n, 1), T, H: H - B, n };
      if (sty !== "bars") {
        S.forEach((s) => {
          let path = "", pen = false;
          s.values.forEach((v, i) => { if (v == null) { pen = false; return; } path += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1); pen = true; });
          if (sty === "area") {
            // each unbroken run of samples, closed down to zero (a gap stays a gap)
            let run = [];
            const close = () => { if (run.length) g += '<path class="fwhca-area c-' + esc(s.key) + '" d="M' + run[0][0] + " " + y(0).toFixed(1) +
              run.map((p) => "L" + p[0] + " " + p[1]).join("") + "L" + run[run.length - 1][0] + " " + y(0).toFixed(1) + 'Z"/>'; run = []; };
            s.values.forEach((v, i) => { if (v == null) close(); else run.push([x(i).toFixed(1), y(v).toFixed(1)]); });
            close();
          }
          g += '<path class="fwhca-line c-' + esc(s.key) + (s.extra ? " fwhca-x" : "") + '" d="' + path + '"><title>' + esc(s.label) + "</title></path>";
        });
      } else if (stack) {
        const bw = Math.max(1, cw * 0.7);
        d.labels.forEach((t, i) => {
          let up = 0, down = 0;
          S.forEach((s) => {
            const real = s.values[i], v = drawn(s, real);
            if (v == null || v === 0) return;
            const from = v > 0 ? up : down, to = from + v;
            if (v > 0) up = to; else down = to;
            g += '<rect class="fwhca-bar-r c-' + esc(s.key) + '" x="' + (x(i) - bw / 2).toFixed(1) + '" width="' + bw.toFixed(1) +
                 '" y="' + Math.min(y(from), y(to)).toFixed(1) + '" height="' + Math.max(0.5, Math.abs(y(to) - y(from))).toFixed(1) +
                 '"/>';
          });
        });
      } else {
        const bw = Math.max(1, cw * 0.8 / Math.max(S.length, 1));
        S.forEach((s, k) => s.values.forEach((v, i) => {
          if (v == null) return;
          const bx = x(i) - cw * 0.4 + k * bw;
          g += '<rect class="fwhca-bar-r c-' + esc(s.key) + (s.extra ? " fwhca-x" : "") + '" x="' + bx.toFixed(1) + '" width="' + bw.toFixed(1) + '" y="' + Math.min(y(v), y(0)).toFixed(1) +
               '" height="' + Math.max(0.5, Math.abs(y(v) - y(0))).toFixed(1) + '"/>';
        }));
      }
      P.forEach((s) => {
        let path = "", pen = false;
        s.values.forEach((v, i) => { if (v == null) { pen = false; return; } path += (pen ? "L" : "M") + x(i).toFixed(1) + " " + yp(v).toFixed(1); pen = true; });
        g += '<path class="fwhca-line c-' + esc(s.key) + '" d="' + path + '"><title>' + esc(s.label) + "</title></path>";
      });
      return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Cloud energy chart in ' + esc(d.unit) + '">' +
             '<text class="fwhca-ax fwhca-unit" transform="translate(12 ' + ((T + H - B) / 2) + ') rotate(-90)" text-anchor="middle">' + esc(d.unit) + "</text>" + g +
             '<line class="fwhca-guide" y1="' + T + '" y2="' + (H - B) + '" x1="-9" x2="-9"/></svg>';
    }

    // Lines for a day, bars for longer periods, until the viewer picks one.
    function style(d) { return st.style || (d.chart === "line" ? "line" : "bars"); }

    // The readout: hover (or tap, on a phone) anywhere on the chart for every shown value
    // at that time, as the bridge's own Analytics does.
    let geo = null;
    const plot = $(".fwhca-plot"), tip = $(".fwhca-tip");
    function hideTip() { tip.hidden = true; const g = plot.querySelector(".fwhca-guide"); if (g) g.setAttribute("x1", -9), g.setAttribute("x2", -9); }
    function showTip(ev) {
      const d = st.data, svg = plot.querySelector("svg");
      if (!geo || !svg || !d || d.error || d.empty) return;
      const r = svg.getBoundingClientRect(), k = geo.W / r.width;
      const i = Math.floor(((ev.clientX - r.left) * k - geo.L) / geo.cw);
      if (i < 0 || i >= geo.n) { hideTip(); return; }
      tipAt(i, ev.clientX, ev.clientY);
    }
    function tipAt(i, cx, cy) {
      const d = st.data, svg = plot.querySelector("svg");
      const gx = (geo.L + geo.cw * (i + 0.5)).toFixed(1), guide = svg.querySelector(".fwhca-guide");
      guide.setAttribute("x1", gx); guide.setAttribute("x2", gx);
      tip.innerHTML = '<b>' + esc(long(d.labels[i], d)) + "</b>" + shown(d).map((s) => '<span><i class="c-' + esc(s.key) + '"></i>' +
        esc(s.label) + ": " + esc(fmt(s.values[i], s.unit || d.unit)) + "</span>").join("");
      tip.hidden = false;
      const pr = plot.getBoundingClientRect(), px = cx - pr.left, w = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(pr.width - w, px + (px > pr.width / 2 ? -w - 12 : 12))) + "px";
      tip.style.top = Math.max(0, cy - pr.top - tip.offsetHeight / 2) + "px";
    }
    // A host's own time picker (Day views): the readout at the slot nearest "HH:MM", again
    // after every load until showAt(null).
    function showAt(hhmm) { st.at = hhmm || null; if (st.at) applyAt(); else hideTip(); }
    function applyAt() {
      const d = st.data, svg = plot.querySelector("svg");
      if (!st.at || !geo || !svg || !d || d.error || d.empty || !(d.period === "day5" || d.period === "dayhour")) return;
      const mins = (t) => { const m = /(\d\d):(\d\d)/.exec(String(t)); return m ? +m[1] * 60 + +m[2] : null; };
      const want = mins(st.at);
      let best = -1, gap = Infinity;
      d.labels.forEach((t, i) => { const m = mins(t); if (m != null && Math.abs(m - want) < gap) { gap = Math.abs(m - want); best = i; } });
      if (best < 0) return;
      const r = svg.getBoundingClientRect();
      tipAt(best, r.left + (geo.L + geo.cw * (best + 0.5)) * r.width / geo.W, r.top + r.height / 3);
    }
    plot.addEventListener("pointermove", showTip);
    plot.addEventListener("pointerdown", showTip);
    plot.addEventListener("pointerleave", (ev) => { if (ev.pointerType === "mouse") hideTip(); });

    // redraw at the new width when the panel is resized (rotation, sidebar)
    let lastW = 0;
    if (window.ResizeObserver) new ResizeObserver(() => {
      const w = $(".fwhca-chart").clientWidth;
      if (Math.abs(w - lastW) > 8) { lastW = w; if (!st.busy) render(); }
    }).observe(el);
    load();
    // The shown period as a file: every series the cloud returned (chips only hide them on
    // the chart), the labels as the cloud gave them, null left empty.
    function exportData(fmt) {
      const d = st.data;
      if (!d || d.error || st.busy) return false;
      const name = "fwh-cloud-" + d.period + (d.period === "lifetime" ? "" : d.period === "custom"
        ? "-" + d.from.replace(":", "") + "-" + d.to.replace(":", "") : "-" + d.date) + "." + fmt;
      let body, type;
      if (fmt === "json") {
        body = JSON.stringify({ source: d.source, period: d.period, date: d.date, from: d.from, to: d.to, unit: d.unit, note: d.note,
          labels: d.labels, series: d.series, flows: d.flows || null, raw: d.raw || {}, fetched_at: d.fetched_at || null }, null, 2);
        type = "application/json";
      } else {
        const cell = (v) => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
        const head = [d.period === "day5" || d.period === "dayhour" || d.res === "5min" || d.res === "hour" ? "time" : "date"]
          .concat(d.series.map((s) => s.label + " (" + (s.unit || d.unit) + ")"));
        body = [head].concat(d.labels.map((t, i) => [t].concat(d.series.map((s) => s.values[i]))))
          .map((r) => r.map(cell).join(",")).join("\n") + "\n";
        type = "text/csv";
      }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([body], { type: type + ";charset=utf-8" }));
      a.download = name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      return true;
    }

    return { reload: () => load(true), exportData, setPeriod, period: () => st.period, setStyle,
             setStacked, setDate, date: () => st.date, showAt, setRange, range: () => st.range,
             style: () => (st.data && !st.data.error ? style(st.data) : st.style) };
  }

  function nice(x) { const p = Math.pow(10, Math.floor(Math.log10(x))); const m = x / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p; }
  // Dates in the viewer's own format (5 Jan, Jan 5, …) from the browser's locale. A label is
  // a day on the site's calendar, so it is formatted as UTC: no shift into this browser's zone.
  function dateText(t, opts) {
    const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(String(t));
    if (!m) return String(t);
    return new Intl.DateTimeFormat(undefined, Object.assign({ timeZone: "UTC" }, opts))
      .format(new Date(Date.UTC(+m[1], +m[2] - 1, +(m[3] || 1))));
  }
  const DAY = { day: "numeric", month: "short" }, FULL = { day: "numeric", month: "short", year: "numeric" };
  // the axis: times stay 24-hour, as the site's own clock
  function short(t, d) {
    t = String(t);
    const period = d.period === "custom" ? { "5min": "day5", hour: "day5", day: "month", month: "custom-month" }[d.res] : d.period;
    if (period === "day5") return t.split(" ").pop().slice(0, 5);
    if (period === "week" || period === "month") return dateText(t, DAY);
    if (period === "year") return dateText(t, { month: "short" });
    if (period === "custom-month") return dateText(t, { month: "short", year: "2-digit" });
    return t;
  }
  // a custom range in the status line: "5 Nov 2026, 22:00 – 6 Nov 2026, 02:00"
  function rangeText(d) {
    const one = (v) => dateText(v.slice(0, 10), FULL) + ", " + v.slice(11, 16);
    return one(d.from) + " – " + one(d.to);
  }
  // the readout's heading: the whole date
  function long(t, d) {
    t = String(t);
    const wd = Object.assign({ weekday: "short" }, FULL);
    if (d.period === "day5" || (d.period === "custom" && (d.res === "5min" || d.res === "hour"))) {
      const p = t.split(" "); return p.length > 1 ? dateText(p[0], wd) + " " + p[1].slice(0, 5) : t;
    }
    if (d.period === "custom") return d.res === "day" ? dateText(t, wd) : dateText(t, { month: "long", year: "numeric" });
    if (d.period === "dayhour") return dateText(d.date, wd) + " " + t;
    if (d.period === "week" || d.period === "month") return dateText(t, wd);
    if (d.period === "year") return dateText(t, { month: "long", year: "numeric" });
    return t;
  }

  window.FWHCloudAnalytics = { mount, PERIODS: PERIODS.map((p) => p.slice()) };
})();
