/* FranklinWH cloud analytics: the period picker and chart, drawn inside a host's page.
 *
 * The bridge serves this file and cloud-analytics.css at /cloud-analytics/, includes both,
 * and calls FWHCloudAnalytics.mount(el, {endpoint: "api/analytics/cloud"}). The endpoint
 * takes ?period=&date= (and anything the host adds through params(), such as its gateway)
 * and returns franklinwh_ha_cloud_analytics.build()'s payload, or {error: "..."}. Dates
 * and their steps come from the payload (the site's own calendar), never from this
 * browser's clock in UTC.
 */
(function () {
  "use strict";

  const PERIODS = [["day5", "Day (5-min)"], ["dayhour", "Day (hourly)"], ["week", "Week"],
                   ["month", "Month"], ["year", "Year"], ["lifetime", "Lifetime"]];
  const KEY = "fwh-cloud-analytics:period";
  const KEY_STACK = "fwh-cloud-analytics:stacked";   // "1": bars stacked, one column per bucket
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } }
  };
  // Today in this browser's own zone (not toISOString, which is UTC). Only the first load
  // uses it; after that the payload's date and nav are the site's calendar.
  const localToday = () => { const d = new Date(); const p = (n) => String(n).padStart(2, "0");
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()); };
  const fmt = (v, unit) => v == null ? "no data" : (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)) + " " + unit;

  function mount(el, options) {
    const o = Object.assign({ endpoint: "api/analytics/cloud", params: null, sourceLabel: "the FranklinWH cloud" }, options || {});
    const st = { period: store.get(KEY) || "day5", date: localToday(), data: null, busy: false,
                 stacked: store.get(KEY_STACK) === "1" };
    if (!PERIODS.some((p) => p[0] === st.period)) st.period = "day5";
    el.classList.add("fwhca");
    el.innerHTML =
      '<div class="fwhca-bar"><select class="fwhca-period" aria-label="Period">' +
      PERIODS.map((p) => '<option value="' + p[0] + '">' + p[1] + "</option>").join("") +
      '</select><div class="fwhca-nav"><button type="button" data-step="prev" aria-label="Previous period">‹</button>' +
      '<input type="date" aria-label="Date"><button type="button" data-step="next" aria-label="Next period">›</button>' +
      '<button type="button" data-stack aria-pressed="false" aria-label="Stacked bars" title="Stacked: where the energy came from above zero, where it went below">' +
      '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path d="M3 2h4v5H3zM3 9h4v5H3zM9 5h4v3H9zM9 10h4v4H9z" fill="currentColor"/></svg></button>' +
      '<button type="button" data-refresh aria-label="Refresh" title="Refresh">↻</button></div></div>' +
      '<p class="fwhca-status" aria-live="polite"></p><div class="fwhca-chart"></div>' +
      '<div class="fwhca-legend"></div><p class="fwhca-note"></p>';
    const $ = (s) => el.querySelector(s);
    const dateIn = $("input[type=date]");

    el.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b || st.busy) return;
      if (b.dataset.step && st.data && st.data.nav[b.dataset.step]) { st.date = st.data.nav[b.dataset.step]; load(); }
      else if ("refresh" in b.dataset) load(true);
      else if ("stack" in b.dataset) { st.stacked = !st.stacked; store.set(KEY_STACK, st.stacked ? "1" : "0"); render(); }
    });
    const periodIn = $(".fwhca-period");
    periodIn.addEventListener("change", () => { st.period = periodIn.value; store.set(KEY, st.period); load(); });
    dateIn.addEventListener("change", () => { if (dateIn.value) { st.date = dateIn.value; load(); } });

    async function load(refresh) {
      st.busy = true; render();
      const q = new URLSearchParams(Object.assign({ period: st.period, date: st.date },
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
      periodIn.value = st.period;
      periodIn.disabled = st.busy;
      const life = st.period === "lifetime";
      $(".fwhca-nav").hidden = life;
      dateIn.value = st.date;
      dateIn.max = localToday();
      $("[data-step=prev]").disabled = !d || !!d.error || !d.nav || !d.nav.prev;
      $("[data-step=next]").disabled = !d || !!d.error || !d.nav || !d.nav.next;
      const stackBtn = $("[data-stack]");
      stackBtn.hidden = !d || !!d.error || d.chart !== "bars";
      stackBtn.setAttribute("aria-pressed", String(st.stacked));
      const status = $(".fwhca-status");
      status.classList.toggle("fwhca-err", !!(d && d.error));
      if (st.busy) status.textContent = "Loading from " + o.sourceLabel + "…";
      else if (!d) status.textContent = "";
      else if (d.error) status.textContent = d.error;
      else status.textContent = "Showing cloud data from " + o.sourceLabel + (life ? "" : " · " + d.date) +
        (d.fetched_at ? " · read " + new Date(d.fetched_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "");
      const ok = d && !d.error && !st.busy;
      $(".fwhca-chart").innerHTML = ok ? (d.empty ? '<p class="fwhca-empty">No cloud data for this period.</p>' : chart(d)) : "";
      $(".fwhca-legend").innerHTML = ok && !d.empty ? legend(d) : "";
      $(".fwhca-note").textContent = ok ? [d.note, st.stacked && d.chart === "bars" && !d.empty
        ? "Stacked: where the energy came from above zero (solar, battery, grid import), where it went below (home, battery charge, grid export)." : null]
        .filter(Boolean).join(" ") : "";
    }

    // Series with nothing but null or 0 (a site with no generator) are left out.
    const shown = (d) => d.series.filter((s) => s.values.some((v) => v != null && v !== 0));

    function legend(d) {
      return shown(d).map((s) => '<span class="fwhca-key"><i class="c-' + esc(s.key) + '"></i>' + esc(s.label) +
        (s.evidence === "INFERRED" ? ' <abbr title="Inferred from the field name; never checked">(inferred)</abbr>' : "") +
        (s.derived ? ' <abbr title="Added up from the cloud\'s 5-minute flows">≈</abbr>' : "") + "</span>").join("");
    }

    function chart(d) {
      // drawn at the panel's own width, so axis text stays readable on a phone
      const S = shown(d), n = d.labels.length, W = Math.max(300, Math.round($(".fwhca-chart").clientWidth || 720)),
            H = W < 520 ? 220 : 260, L = 44, R = 8, T = 24, B = 28;
      const stack = st.stacked && d.chart === "bars";
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
      const every = Math.ceil(n / (W < 520 ? 4 : 8));
      d.labels.forEach((t, i) => { if (i % every === 0) g += '<text class="fwhca-ax" x="' + x(i) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(short(t, d.period)) + "</text>"; });
      if (d.chart === "line") {
        S.forEach((s) => {
          let path = "", pen = false;
          s.values.forEach((v, i) => { if (v == null) { pen = false; return; } path += (pen ? "L" : "M") + x(i).toFixed(1) + " " + y(v).toFixed(1); pen = true; });
          g += '<path class="fwhca-line c-' + esc(s.key) + '" d="' + path + '"><title>' + esc(s.label) + "</title></path>";
        });
        // one invisible column per sample, so hovering anywhere shows that time's values
        d.labels.forEach((t, i) => { g += '<rect class="fwhca-hit" x="' + (x(i) - cw / 2) + '" y="' + T + '" width="' + cw + '" height="' + (H - T - B) + '"><title>' +
          esc(t + "\n" + S.map((s) => s.label + ": " + fmt(s.values[i], d.unit)).join("\n")) + "</title></rect>"; });
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
                 '"><title>' + esc(t + " · " + s.label + ": " + fmt(real, d.unit)) + "</title></rect>";
          });
        });
      } else {
        const bw = Math.max(1, cw * 0.8 / Math.max(S.length, 1));
        S.forEach((s, k) => s.values.forEach((v, i) => {
          if (v == null) return;
          const bx = x(i) - cw * 0.4 + k * bw;
          g += '<rect class="fwhca-bar-r c-' + esc(s.key) + '" x="' + bx.toFixed(1) + '" width="' + bw.toFixed(1) + '" y="' + Math.min(y(v), y(0)).toFixed(1) +
               '" height="' + Math.max(0.5, Math.abs(y(v) - y(0))).toFixed(1) + '"><title>' + esc(d.labels[i] + " · " + s.label + ": " + fmt(v, d.unit)) + "</title></rect>";
        }));
      }
      return '<svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Cloud energy chart in ' + esc(d.unit) + '">' +
             '<text class="fwhca-ax" x="4" y="12">' + esc(d.unit) + "</text>" + g + "</svg>";
    }

    // redraw at the new width when the panel is resized (rotation, sidebar)
    let lastW = 0;
    if (window.ResizeObserver) new ResizeObserver(() => {
      const w = $(".fwhca-chart").clientWidth;
      if (Math.abs(w - lastW) > 8) { lastW = w; if (!st.busy) render(); }
    }).observe(el);
    load();
    return { reload: () => load(true) };
  }

  function nice(x) { const p = Math.pow(10, Math.floor(Math.log10(x))); const m = x / p; return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p; }
  function short(t, period) {
    t = String(t);
    if (period === "day5") return t.split(" ").pop().slice(0, 5);
    if (period === "week" || period === "month") return t.slice(5);
    return t;
  }

  window.FWHCloudAnalytics = { mount };
})();
