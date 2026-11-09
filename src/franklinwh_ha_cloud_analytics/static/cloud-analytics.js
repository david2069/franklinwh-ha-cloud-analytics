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
 * the chart that many pixels tall at any width, to match the host's own chart.
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
                              periodPicker: true, period: null, height: null }, options || {});
    const st = { period: o.period || store.get(KEY) || "day5", date: localToday(), data: null, busy: false,
                 stacked: store.get(KEY_STACK) === "1", style: STYLES.includes(store.get(KEY_STYLE)) ? store.get(KEY_STYLE) : null,
                 hidden: (() => { try { const h = JSON.parse(store.get(KEY_HIDDEN) || "[]"); return Array.isArray(h) ? h : []; } catch (e) { return []; } })() };
    if (!PERIODS.some((p) => p[0] === st.period)) st.period = "day5";
    el.classList.add("fwhca");
    el.innerHTML =
      '<div class="fwhca-bar">' + (o.periodPicker ? '<select class="fwhca-period" aria-label="Period">' +
      PERIODS.map((p) => '<option value="' + p[0] + '">' + p[1] + "</option>").join("") +
      "</select>" : "<span></span>") + '<div class="fwhca-nav"><button type="button" data-step="prev" aria-label="Previous period">‹</button>' +
      '<input type="date" aria-label="Date"><button type="button" data-step="next" aria-label="Next period">›</button>' +
      '<button type="button" data-today title="Back to today">Today</button>' +
      '</div></div>' +
      '<div class="fwhca-statusbar"><p class="fwhca-status" aria-live="polite"></p>' +
      '<button type="button" data-refresh aria-label="Refresh" title="Refresh">↻</button></div><div class="fwhca-plot"><div class="fwhca-chart"></div><div class="fwhca-tip" hidden></div></div>' +
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
        const k = b.dataset.key;
        st.hidden = st.hidden.includes(k) ? st.hidden.filter((h) => h !== k) : st.hidden.concat(k);
        store.set(KEY_HIDDEN, JSON.stringify(st.hidden)); render();
      }
      else if ("stack" in b.dataset) { st.stacked = !st.stacked; store.set(KEY_STACK, st.stacked ? "1" : "0"); render(); }
    });
    const periodIn = $(".fwhca-period");
    if (periodIn) periodIn.addEventListener("change", () => { st.period = periodIn.value; store.set(KEY, st.period); load(); });
    function setPeriod(p) {
      if (!PERIODS.some((x) => x[0] === p) || p === st.period) return;
      st.period = p;
      if (o.periodPicker) store.set(KEY, p);
      load();
    }
    dateIn.addEventListener("change", () => { if (dateIn.value) { st.date = dateIn.value; load(); } });

    async function load(refresh) {
      st.busy = true; render();
      const q = new URLSearchParams(Object.assign({ period: st.period }, st.date ? { date: st.date } : {},
        refresh ? { refresh: "1" } : {}, typeof o.params === "function" ? o.params() : o.params || {}));
      try {
        const r = await fetch(o.endpoint + (o.endpoint.includes("?") ? "&" : "?") + q);
        const j = await r.json().catch(() => ({ error: "HTTP " + r.status }));
        st.data = r.ok && !j.error ? j : { error: j.error || j.detail || "HTTP " + r.status };
        if (!st.data.error) st.date = st.data.date;
      } catch (e) { st.data = { error: "Could not reach the bridge: " + e.message }; }
      st.busy = false; render();
    }

    function render() {
      const d = st.data;
      if (periodIn) { periodIn.value = st.period; periodIn.disabled = st.busy; }
      const life = st.period === "lifetime";
      $(".fwhca-nav").hidden = life;
      dateIn.value = st.date || "";
      dateIn.max = localToday();
      $("[data-step=prev]").disabled = !d || !!d.error || !d.nav || !d.nav.prev;
      $("[data-step=next]").disabled = !d || !!d.error || !d.nav || !d.nav.next;
      $("[data-today]").disabled = !d || !!d.error || !!d.current;
      const sty = d && !d.error ? style(d) : null;
      $(".fwhca-seg").hidden = !sty;
      STYLES.forEach((k) => $("[data-style=" + k + "]").setAttribute("aria-pressed", String(sty === k)));
      const stackBtn = $("[data-stack]");
      stackBtn.hidden = sty !== "bars";
      stackBtn.setAttribute("aria-pressed", String(st.stacked));
      const status = $(".fwhca-status");
      status.classList.toggle("fwhca-err", !!(d && d.error));
      if (st.busy) status.textContent = "Loading from " + o.sourceLabel + "…";
      else if (!d) status.textContent = "";
      else if (d.error) status.textContent = d.error;
      else status.textContent = "Showing cloud data from " + o.sourceLabel + (life ? "" : " · " + dateText(d.date, FULL)) +
        (d.fetched_at ? " · read " + new Date(d.fetched_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
      const ok = d && !d.error && !st.busy;
      $(".fwhca-chart").innerHTML = ok ? (d.empty ? '<p class="fwhca-empty">No cloud data for this period.</p>' : chart(d)) : "";
      $(".fwhca-legend").innerHTML = ok && !d.empty ? legend(d) : "";
      hideTip();
      $(".fwhca-note").textContent = ok ? [d.note, st.stacked && sty === "bars" && !d.empty
        ? "Stacked: where the energy came from above zero (solar, battery, grid import), where it went below (home, battery charge, grid export)." : null]
        .filter(Boolean).join(" ") : "";
    }

    // Series with nothing but null or 0 (a site with no generator) are left out; the chips
    // list the rest, and the chart draws the ones not switched off.
    const present = (d) => d.series.filter((s) => s.values.some((v) => v != null && v !== 0));
    const shown = (d) => present(d).filter((s) => !st.hidden.includes(s.key));

    function legend(d) {
      return present(d).map((s) => {
        const on = !st.hidden.includes(s.key);
        return '<button type="button" class="fwhca-key" data-key="' + esc(s.key) + '" aria-pressed="' + on + '" title="' + (on ? "Hide " : "Show ") + esc(s.label) + '">' +
          '<i class="c-' + esc(s.key) + '"></i>' + esc(s.label) +
          (s.evidence === "INFERRED" ? ' <abbr title="Inferred from the field name; never checked">(inferred)</abbr>' : "") +
          (s.derived ? ' <abbr title="Added up from the cloud\'s 5-minute flows">≈</abbr>' : "") + "</button>";
      }).join("");
    }

    function chart(d) {
      // drawn at the panel's own width, so axis text stays readable on a phone. SoC (axis
      // "pct") is a line on its own 0-100 % axis at the right, whatever the style.
      const P = shown(d).filter((s) => s.axis === "pct"), S = shown(d).filter((s) => s.axis !== "pct"),
            n = d.labels.length, W = Math.max(300, Math.round($(".fwhca-chart").clientWidth || 720)),
            H = o.height || (W < 520 ? 220 : 260), L = 44, R = P.length ? 36 : 8, T = 24, B = 28;
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
      if (P.length) {
        [0, 50, 100].forEach((v) => { g += '<text class="fwhca-ax fwhca-pct" x="' + (W - R + 6) + '" y="' + (yp(v) + 4) + '">' + v + "</text>"; });
        g += '<text class="fwhca-ax fwhca-pct" x="' + (W - 4) + '" y="12" text-anchor="end">%</text>';
      }
      const every = Math.ceil(n / (W < 520 ? 4 : 8));
      d.labels.forEach((t, i) => { if (i % every === 0) g += '<text class="fwhca-ax" x="' + x(i) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(short(t, d.period)) + "</text>"; });
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
          g += '<path class="fwhca-line c-' + esc(s.key) + '" d="' + path + '"><title>' + esc(s.label) + "</title></path>";
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
          g += '<rect class="fwhca-bar-r c-' + esc(s.key) + '" x="' + bx.toFixed(1) + '" width="' + bw.toFixed(1) + '" y="' + Math.min(y(v), y(0)).toFixed(1) +
               '" height="' + Math.max(0.5, Math.abs(y(v) - y(0))).toFixed(1) + '"/>';
        }));
      }
      P.forEach((s) => {
        let path = "", pen = false;
        s.values.forEach((v, i) => { if (v == null) { pen = false; return; } path += (pen ? "L" : "M") + x(i).toFixed(1) + " " + yp(v).toFixed(1); pen = true; });
        g += '<path class="fwhca-line c-' + esc(s.key) + '" d="' + path + '"><title>' + esc(s.label) + "</title></path>";
      });
      return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Cloud energy chart in ' + esc(d.unit) + '">' +
             '<text class="fwhca-ax" x="4" y="12">' + esc(d.unit) + "</text>" + g +
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
      const gx = (geo.L + geo.cw * (i + 0.5)).toFixed(1), guide = svg.querySelector(".fwhca-guide");
      guide.setAttribute("x1", gx); guide.setAttribute("x2", gx);
      tip.innerHTML = '<b>' + esc(long(d.labels[i], d)) + "</b>" + shown(d).map((s) => '<span><i class="c-' + esc(s.key) + '"></i>' +
        esc(s.label) + ": " + esc(fmt(s.values[i], s.unit || d.unit)) + "</span>").join("");
      tip.hidden = false;
      const pr = plot.getBoundingClientRect(), px = ev.clientX - pr.left, w = tip.offsetWidth;
      tip.style.left = Math.max(0, Math.min(pr.width - w, px + (px > pr.width / 2 ? -w - 12 : 12))) + "px";
      tip.style.top = Math.max(0, ev.clientY - pr.top - tip.offsetHeight / 2) + "px";
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
      const name = "fwh-cloud-" + d.period + (d.period === "lifetime" ? "" : "-" + d.date) + "." + fmt;
      let body, type;
      if (fmt === "json") {
        body = JSON.stringify({ source: d.source, period: d.period, date: d.date, unit: d.unit, note: d.note,
          labels: d.labels, series: d.series, fetched_at: d.fetched_at || null }, null, 2);
        type = "application/json";
      } else {
        const cell = (v) => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
        const head = [d.period === "day5" || d.period === "dayhour" ? "time" : "date"]
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

    return { reload: () => load(true), exportData, setPeriod, period: () => st.period };
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
  function short(t, period) {
    t = String(t);
    if (period === "day5") return t.split(" ").pop().slice(0, 5);
    if (period === "week" || period === "month") return dateText(t, DAY);
    if (period === "year") return dateText(t, { month: "short" });
    return t;
  }
  // the readout's heading: the whole date
  function long(t, d) {
    t = String(t);
    const wd = Object.assign({ weekday: "short" }, FULL);
    if (d.period === "day5") { const p = t.split(" "); return p.length > 1 ? dateText(p[0], wd) + " " + p[1].slice(0, 5) : t; }
    if (d.period === "dayhour") return dateText(d.date, wd) + " " + t;
    if (d.period === "week" || d.period === "month") return dateText(t, wd);
    if (d.period === "year") return dateText(t, { month: "long", year: "numeric" });
    return t;
  }

  window.FWHCloudAnalytics = { mount, PERIODS: PERIODS.map((p) => p.slice()) };
})();
