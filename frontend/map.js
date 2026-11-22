// Coordinator dashboard: every panel at once, any tile can be enlarged (⤢).
//   header   the selected casualty: priority, position, tourniquet, mobility, people to send, question
//   tiles    Evacuation order · Casualty (MIST, plan) · Map · 3D casualty · Location · Sound · Response
// Compact tiles hide their details (".more"); an enlarged tile shows them.
// Data: /ws state for the list, pins and header; panels.js loads the per-report pictures.
const $ = (id) => document.getElementById(id);
const COLORS = { 1: "#e5484d", 2: "#f0a33a", 3: "#4cc38a", 9: "#8b9a94" };
const SHORT = { walks: "can walk", assisted: "needs help", litter: "stretcher", trapped: "trapped", unknown: "unknown" };
let state = null, offset = 0, selected = null, lastManual = 0, lastSeenUpdate = 0, mode = null;

// ---------------------------------------------------------------- map
const map = L.map("map", { zoomControl: true }).setView([48.8435, 2.4355], 15);
const OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTR = "&copy; OpenStreetMap contributors";
// Default: tiles drawn on this laptop from our OSM / IGN data, so the map works with no internet.
const offline = L.tileLayer("/tiles/{z}/{x}/{y}.png", { minZoom: 12, maxNativeZoom: 17, maxZoom: 19, minNativeZoom: 13,
  bounds: L.latLngBounds([48.830, 2.405], [48.865, 2.465]),        // the area we have data for
  attribution: OSM_ATTR + " · IGN · drawn offline" }).addTo(map);
const dark = L.tileLayer(OSM_URL, { maxZoom: 19, attribution: OSM_ATTR, className: "dark-tiles" });
const osm = L.tileLayer(OSM_URL, { maxZoom: 19, attribution: OSM_ATTR });
L.control.layers({ "Offline (local data)": offline, "Dark (online)": dark, "OpenStreetMap (online)": osm }, {}, { position: "topleft" }).addTo(map);
L.control.scale({ imperial: false }).addTo(map);
function zoomClass() { map.getContainer().classList.toggle("far", map.getZoom() < 16); }
map.on("zoomend", zoomClass); zoomClass();

const heatLayer = L.layerGroup().addTo(map);
const dangerLayer = L.layerGroup().addTo(map);   // under the pins
const routeLayer = L.layerGroup().addTo(map);    // walking routes to the CCP, medic routes
const reportLayer = L.layerGroup().addTo(map);
const candLayer = L.layerGroup().addTo(map);     // candidate areas (Location tab)
const lmLayer = L.layerGroup().addTo(map);
let ccpMarker = null, heatKey = null;

fetch("/api/landmarks").then((r) => r.json()).then((feats) => {
  feats.forEach((f) => {
    const label = f.name || f.type.replace("_", " ");
    const big = ["keep", "castle", "water_tower"].includes(f.type);
    L.marker([f.lat, f.lon], { interactive: false, icon: L.divIcon({
      className: "", html: `<span class="lm ${big ? "big" : ""}"><i></i><span class="n">${esc(label)}</span></span>`, iconSize: null }) }).addTo(lmLayer);
  });
});

// ---------------------------------------------------------------- helpers
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
function now() { return Date.now() + offset; }
function fmtElapsed(ms) { const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000); return `${m}:${String(s).padStart(2, "0")}`; }
function tqClass(ms) { const m = ms / 60000, w = (state && state.tq_warn_min) || [60, 90, 120]; return m >= w[2] ? "w3" : m >= w[1] ? "w2" : m >= w[0] ? "w1" : "w0"; }
function areasTxt(p) { const n = Math.max(1, p.blobs.filter((b) => b.mass >= 0.12).length); return `${n} area${n > 1 ? "s" : ""}`; }
function fmtDist(d) { return d == null ? "" : d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`; }

function ellipse(b, k = 2) {
  const a = (b.angle * Math.PI) / 180, pts = [];
  const u = [Math.sin(a), Math.cos(a)], v = [Math.cos(a), -Math.sin(a)];
  const mLat = 110540, mLon = 111320 * Math.cos((b.lat * Math.PI) / 180);
  for (let i = 0; i <= 48; i++) {
    const t = (i / 48) * 2 * Math.PI;
    const dx = k * b.sx * Math.cos(t) * u[0] + k * b.sy * Math.sin(t) * v[0];
    const dy = k * b.sx * Math.cos(t) * u[1] + k * b.sy * Math.sin(t) * v[1];
    pts.push([b.lat + dy / mLat, b.lon + dx / mLon]);
  }
  return pts;
}
function ramp(v) {
  const stops = [[0, 90, 20, 130, 0], [0.15, 150, 40, 120, 0.18], [0.5, 230, 90, 60, 0.45], [1, 255, 225, 100, 0.75]];
  for (let i = 1; i < stops.length; i++) {
    if (v <= stops[i][0]) {
      const a = stops[i - 1], b = stops[i], t = (v - a[0]) / (b[0] - a[0]);
      return [0, 1, 2, 3].map((j) => a[j + 1] + t * (b[j + 1] - a[j + 1]));
    }
  }
  return stops[stops.length - 1].slice(1);
}
function heatOverlay(h, layer, colour) {
  const raw = atob(h.data);
  const c = document.createElement("canvas"); c.width = h.w; c.height = h.h;
  const ctx = c.getContext("2d"), img = ctx.createImageData(h.w, h.h);
  for (let i = 0; i < raw.length; i++) {
    const v = raw.charCodeAt(i) / 255;
    if (v < 0.03) continue;
    const [r, g, b, a] = colour(v);
    img.data[i * 4] = r; img.data[i * 4 + 1] = g; img.data[i * 4 + 2] = b; img.data[i * 4 + 3] = a * 255;
  }
  ctx.putImageData(img, 0, 0);
  const bd = h.bounds;
  L.imageOverlay(c.toDataURL(), [[bd.south, bd.west], [bd.north, bd.east]], { opacity: 0.9 }).addTo(layer);
}
function drawHeat(rep) {
  const key = rep ? rep.id + ":" + rep.updated_ms : null;
  if (key === heatKey) return;
  heatKey = key;
  heatLayer.clearLayers();
  if (!rep || !rep.heat) return;
  heatOverlay(rep.heat, heatLayer, ramp);
}

// "Audio match": where the audio ALONE fits (echoes, noise level, space, sounds), in cyan.
const audioLayer = L.layerGroup();
let audioOn = false, audioHeat = null;
function drawAudio() {
  audioLayer.clearLayers();
  if (audioOn && audioHeat) heatOverlay(audioHeat, audioLayer, (v) => [51, 225, 255, 0.08 + 0.62 * v]);
}
Panels.onSurround = (s) => { audioHeat = s && s.audio_only ? s.audio_only.heat : null; drawAudio(); };
$("audioBtn").onclick = (e) => {
  audioOn = !audioOn;
  e.target.classList.toggle("on", audioOn);
  if (audioOn) { map.addLayer(audioLayer); map.removeLayer(heatLayer); } else { map.removeLayer(audioLayer); map.addLayer(heatLayer); }
  drawAudio();
};

// ---------------------------------------------------------------- danger zones
// Zones are pinned to the REPORTER (one phone cannot say where the drone / shooter is):
// circle = heard/seen within the typical range, wedge = a direction was given and the
// heading is known. Dashed = heard by the phone, solid = said by the soldier.
// A thick ring = several units' reports overlap: likely source area.
let dangerHidden = new Set();
try { dangerHidden = new Set(JSON.parse(localStorage.getItem("dangerHidden") || "[]")); } catch (e) { /* private mode */ }
function offsetLL(lat, lon, brgDeg, distM) {
  const a = (brgDeg * Math.PI) / 180;
  return [lat + (distM * Math.cos(a)) / 110540, lon + (distM * Math.sin(a)) / (111320 * Math.cos((lat * Math.PI) / 180))];
}
function fmtAge(ms) { const m = Math.round(ms / 60000); return m < 1 ? "just now" : m < 60 ? `${m} min ago` : `${Math.round(m / 60)} h ago`; }
function dangerTip(z) {
  const src = z.source === "audio" ? `heard by the phone (score ${z.conf})` : "said by the soldier";
  return `<b>${esc(z.label)}</b> · ${esc(z.callsign)}<br>${src} · ${fmtAge(now() - z.ms)}`
    + (z.text ? `<br><span class="meta">${esc(z.text)}</span>` : "")
    + (z.doubt ? `<br><span class="meta">doubtful: ${esc(z.doubt)}</span>` : "")
    + `<br><span class="meta">${z.shape === "wedge" ? "direction given" : "somewhere within"} ~${Math.round(z.radius_m)} m of the reporter</span>`;
}
function drawDanger() {
  dangerLayer.clearLayers();
  const dz = state && state.danger;
  if (!dz) return;
  for (const z of dz.zones) {
    if (dangerHidden.has(z.type)) continue;
    const fade = Math.max(0, 1 - (now() - z.ms) / z.ttl_ms);
    if (fade <= 0) continue;
    const st = { color: z.color, weight: 1.5, opacity: 0.35 + 0.55 * fade, fillColor: z.color,
                 fillOpacity: (z.doubt ? 0.04 : 0.1) * fade + 0.02, dashArray: z.source === "audio" ? "5 5" : null };
    let shape, badgeAt;
    if (!z.placed) {      // the reporter's own position is too uncertain to draw an area
      L.marker([z.lat, z.lon], { icon: L.divIcon({ className: "", iconSize: null,
        html: `<span class="dlabel unplaced" style="--c:${z.color}">${esc(z.label)} ?</span>` }) })
        .bindTooltip(dangerTip(z) + `<br><span class="meta">not drawn: reporter position ± ${Math.round(z.pos_r)} m</span>`)
        .addTo(dangerLayer);
      continue;
    }
    if (z.shape === "wedge") {
      const pts = [[z.lat, z.lon]];
      for (let a = -z.half_deg; a <= z.half_deg + 0.1; a += 5) pts.push(offsetLL(z.lat, z.lon, z.bearing_deg + a, z.radius_m));
      shape = L.polygon(pts, st);
      badgeAt = offsetLL(z.lat, z.lon, z.bearing_deg, z.radius_m * 0.7);
    } else {
      shape = L.circle([z.lat, z.lon], { radius: z.radius_m, ...st });
      badgeAt = offsetLL(z.lat, z.lon, 0, z.radius_m);
    }
    shape.bindTooltip(dangerTip(z), { sticky: true }).addTo(dangerLayer);
    L.marker(badgeAt, { interactive: false, icon: L.divIcon({ className: "", iconSize: null,
      html: `<span class="dlabel" style="--c:${z.color};opacity:${0.5 + 0.5 * fade}">${esc(z.label)}</span>` }) }).addTo(dangerLayer);
  }
  for (const h of dz.hotspots) {
    if (dangerHidden.has(h.type)) continue;
    L.circle([h.lat, h.lon], { radius: Math.max(h.radius_m, 25), color: h.color, weight: 3.5, fillColor: h.color, fillOpacity: 0.22 })
      .bindTooltip(`<b>${esc(h.label)}: likely source area</b><br>${h.n_reports} units' reports overlap (${esc(h.reports.join(", "))})`, { sticky: true })
      .addTo(dangerLayer);
  }
  renderLegend(dz);
}
const legend = L.control({ position: "bottomright" });
legend.onAdd = () => { const d = L.DomUtil.create("div", "dlegend"); L.DomEvent.disableClickPropagation(d); return d; };
legend.addTo(map);
function renderLegend(dz) {
  const el = document.querySelector(".dlegend");
  const counts = {};
  dz.zones.forEach((z) => { counts[z.type] = (counts[z.type] || 0) + 1; });
  const rows = Object.entries(dz.types).map(([k, t]) => `<label class="${counts[k] ? "" : "none"}">
      <input type="checkbox" data-t="${k}" ${dangerHidden.has(k) ? "" : "checked"}>
      <i style="background:${t.color}"></i>${esc(t.label)} <b>${counts[k] || ""}</b></label>`).join("");
  el.innerHTML = `<div class="label">Danger zones</div>${rows}
    <div class="meta">dashed = heard by phone · solid = reported<br>thick ring = reports overlap</div>`;
  el.querySelectorAll("input").forEach((cb) => cb.addEventListener("change", () => {
    cb.checked ? dangerHidden.delete(cb.dataset.t) : dangerHidden.add(cb.dataset.t);
    try { localStorage.setItem("dangerHidden", JSON.stringify([...dangerHidden])); } catch (e) { /* ignore */ }
    drawDanger();
  }));
}
function dangerChips(r) {
  const T = (state.danger && state.danger.types) || {};
  const own = [...new Set((r.dangers || []).map((d) => d.type))];
  const near = (r.danger_near || []).filter((t) => !own.includes(t));
  return own.map((t) => `<span class="dchip" style="--c:${T[t].color}">${esc(T[t].label)}</span>`).join("")
    + near.map((t) => `<span class="dchip near" style="--c:${T[t].color}" title="reported by another unit near here">${esc(T[t].label)} near</span>`).join("");
}

// ---------------------------------------------------------------- routes (backend/guide.py)
// Walking casualty: cyan route to the CCP, dotted trail of where the pin has been.
// Casualty who can't walk: dashed amber route for the medic team, CCP -> casualty.
function fmtMin(s) { const m = Math.max(1, Math.round(s / 60)); return `${m} min`; }
function avoidTxt(av) { const T = (state.danger && state.danger.types) || {}; const k = Object.keys(av || {}); return k.length ? "avoids " + k.map((t) => (T[t] || {}).label || t).join(", ") : ""; }
function drawRoutes() {
  routeLayer.clearLayers();
  for (const r of state.reports) {
    const sel = r.id === selected, g = r.guide, d = r.dispatch;
    if (g && g.lat && g.state !== "stopped") {
      const pts = g.lat.map((la, i) => [la, g.lon[i]]);
      L.polyline(pts, { color: "#33e1ff", weight: sel ? 5 : 3, opacity: g.state === "arrived" ? 0.25 : sel ? 0.9 : 0.55, lineCap: "round" })
        .bindTooltip(`<b>${esc(r.callsign || r.id)} walking to the CCP</b><br>${g.left_m} m left · ~${fmtMin(g.eta_s)} · leg ${g.leg}/${g.legs}`
          + (g.detour_m ? `<br>+${g.detour_m} m to ${avoidTxt(g.avoided)}` : "")
          + `<br><span class="meta">${g.mode === "steps" ? "phone counts steps" : "no step counter: position from walking time"}</span>`, { sticky: true })
        .addTo(routeLayer);
      if (g.trail && g.trail.length > 1)
        L.polyline(g.trail, { color: "#ffffff", weight: 2, opacity: 0.7, dashArray: "1 6", lineCap: "round", interactive: false }).addTo(routeLayer);
    }
    if (d && d.lat) {
      const pts = d.lat.map((la, i) => [la, d.lon[i]]);
      L.polyline(pts, { color: "#f0a33a", weight: sel ? 4 : 2.5, opacity: sel ? 0.9 : 0.5, dashArray: "8 6" })
        .bindTooltip(`<b>Medic route to ${esc(r.callsign || r.id)}</b><br>${fmtDist(d.length_m)} · out ~${fmtMin(d.eta_out_s)} · back with stretcher ~${fmtMin(d.eta_back_s)}`
          + (d.detour_m ? `<br>+${d.detour_m} m to ${avoidTxt(d.avoided)}` : ""), { sticky: true })
        .addTo(routeLayer);
    }
  }
}
function routeLine(r) {
  const g = r.guide, d = r.dispatch;
  if (r.at_ccp) return `<div class="route ok">✓ at the CCP</div>`;
  if (g && g.state === "active") return `<div class="route">→ walking to CCP · ${fmtDist(g.left_m)} left · ~${fmtMin(g.eta_s)}${g.detour_m ? " · safe detour" : ""}</div>`;
  if (g && g.state === "lost") return `<div class="route warn">→ lost on the way: re-locating</div>`;
  if (d) return `<div class="route medic">⇢ medic route ${fmtDist(d.length_m)} · ~${fmtMin(d.eta_out_s)} out${d.detour_m ? " · safe detour" : ""}</div>`;
  return "";
}

// ---------------------------------------------------------------- render
function render() {
  if (!state) return;
  const reps = Object.fromEntries(state.reports.map((r) => [r.id, r]));
  const newest = state.reports.reduce((a, r) => (!a || r.updated_ms > a.updated_ms ? r : a), null);
  if (newest && newest.updated_ms > lastSeenUpdate) {
    lastSeenUpdate = newest.updated_ms;
    if (Date.now() - lastManual > 20000 || !selected) select(newest.id, true);
  }
  if (selected && !reps[selected]) selected = null;

  const ccp = state.ccp;
  if (!ccpMarker) ccpMarker = L.marker([ccp.lat, ccp.lon], { icon: L.divIcon({ className: "", html: `<span class="ccp">✚ CCP</span>`, iconSize: null }) }).addTo(map);
  ccpMarker.setLatLng([ccp.lat, ccp.lon]);

  reportLayer.clearLayers();
  for (const r of state.reports) {
    const p = r.position;
    if (!p || p.lat == null) continue;
    const col = COLORS[r.summary.rank] || COLORS[9];
    const sel = r.id === selected;
    p.blobs.forEach((b, i) => {
      L.polygon(ellipse(b), { color: col, weight: sel ? 2.5 : 1.5, opacity: sel ? 1 : 0.5, dashArray: i ? "5 6" : null,
        fillColor: col, fillOpacity: sel ? 0.06 : 0.02, interactive: false }).addTo(reportLayer);
    });
    // Distinct likely spots A / B / C (peaks >= 300 m apart, even inside one broad area).
    if (sel) (p.hyps || []).forEach((h) => {
      L.circle([h.lat, h.lon], { radius: Math.min(h.r80, 600), color: "#33e1ff", weight: 1.2, dashArray: "3 5",
        fillOpacity: 0.03, interactive: false }).addTo(reportLayer);
      L.marker([h.lat, h.lon], { interactive: false, icon: L.divIcon({ className: "",
        html: `<div class="hyp-label">${h.label} <small>${Math.round(h.mass * 100)}%</small></div>`, iconSize: null }) }).addTo(reportLayer);
    });
    const tag = r.summary.tq_ms ? `<span class="tag" data-tq="${r.summary.tq_ms}">TQ ${fmtElapsed(now() - r.summary.tq_ms)}</span>`
                                : `<span class="tag">${esc(r.callsign || r.id)}</span>`;
    const m = L.marker([p.lat, p.lon], { zIndexOffset: sel ? 1000 : 0, icon: L.divIcon({ className: "", iconSize: [40, 50], iconAnchor: [20, 18],
      html: `<div class="pin ${sel ? "sel" : ""}"><div class="dot" style="background:${col}">${r.summary.count ? "P" + r.summary.rank : "?"}</div>${tag}</div>` }) });
    m.on("click", () => { lastManual = Date.now(); select(r.id); });
    m.addTo(reportLayer);
    if (r.truth) {
      L.marker([r.truth.lat, r.truth.lon], { interactive: false, icon: L.divIcon({ className: "", html: `<span class="truth">+</span>`, iconSize: null }) }).addTo(reportLayer);
      L.polyline([[r.truth.lat, r.truth.lon], [p.lat, p.lon]], { color: "#33e1ff", weight: 1, dashArray: "2 4", interactive: false }).addTo(reportLayer);
    }
  }
  drawHeat(reps[selected]);
  drawDanger();
  drawRoutes();
  renderList(reps);
  renderSelected(reps[selected]);
}

function renderList(reps) {
  const live = state.order.map((id) => reps[id]);
  const others = state.reports.filter((r) => !state.order.includes(r.id));
  $("count").textContent = live.length ? `· ${live.length}` : "";
  if (!live.length && !others.length) {
    $("list").innerHTML = `<div class="empty">No casualties reported yet.<br>Speak on <b>/field</b>, or press <b>Simulate report</b> and click the map.</div>`;
    return;
  }
  const row = (r, rank) => {
    const s = r.summary, tq = s.tq_ms, c0 = r.casualties[0];
    const what = c0 ? [c0.mechanism, (c0.injuries || [])[0]].filter(Boolean).join(" · ") : "awaiting details";
    const m0 = c0 && c0.mobility;
    const mob = m0 ? `<span class="mob ${m0.plan}" title="${esc(m0.conflict ? "said: " + m0.label + " · " + m0.conflict : m0.source + ": " + m0.evidence.join("; "))}">${m0.conflict ? "⚠ " : ""}${SHORT[m0.plan]}</span>` : "";
    return `<div class="item ${r.id === selected ? "sel" : ""} ${r.evacuated ? "evac" : ""}" data-id="${r.id}">
      <div class="rank">${rank ?? "–"}</div>
      <div><div class="top">${s.count ? `<span class="pbadge p${s.rank}">P${s.rank}</span>` : ""}
        <span class="name">${esc(r.callsign || r.id)}</span>${s.count > 1 ? `<span class="meta">×${s.count}</span>` : ""}${mob}</div>
        <div class="meta">${esc(what)}</div>${condLine(c0 && c0.condition)}
        ${(r.dangers || []).length || (r.danger_near || []).length ? `<div class="dchips">${dangerChips(r)}</div>` : ""}
        ${routeLine(r)}
        <div class="meta">${r.position ? `± ${Math.round(r.position.radius_m)} m` : "no position"}${r.distance_ccp != null ? " · " + fmtDist(r.distance_ccp) + " to CCP" : ""}${r.question ? " · asking…" : ""}</div></div>
      <div class="tq ${tq ? tqClass(now() - tq) : ""}" ${tq ? `data-tq="${tq}"` : ""}>${tq ? fmtElapsed(now() - tq) + "<small>TQ</small>" : ""}</div>
    </div>`;
  };
  $("list").innerHTML = live.map((r, i) => row(r, i + 1)).join("") + others.map((r) => row(r, null)).join("");
  document.querySelectorAll(".item").forEach((el) => el.addEventListener("click", () => { lastManual = Date.now(); select(el.dataset.id, false, true); }));
}

// ---------------------------------------------------------------- selected casualty
function ago(ms) {
  const s = Math.max(0, Math.round((now() - ms) / 1000));
  return s < 60 ? `${s} s ago` : s < 3600 ? `${Math.floor(s / 60)} min ago` : new Date(ms).toTimeString().slice(0, 5);
}

// New data for the casualty on screen: flash the tiles so the coordinator sees it changed.
let shown = { id: null, ms: 0 };
function flashIfUpdated(r) {
  if (shown.id === r.id && r.updated_ms > shown.ms)
    document.querySelectorAll("#grid .tile:not(#tList):not(#tMap)").forEach((t) => {
      t.classList.remove("flash"); void t.offsetWidth; t.classList.add("flash");
    });
  shown = { id: r.id, ms: r.updated_ms };
}

function renderSelected(r) {
  if (!r) {
    candLayer.clearLayers(); Panels.load(null);
    $("head").innerHTML = `<span class="muted">Select a casualty in the list or on the map.</span>`;
    $("overview").innerHTML = `<div class="empty">No casualty selected.</div>`;
    $("cardMeta").textContent = ""; $("locMeta").textContent = "";
    return;
  }
  renderHead(r);
  renderOverview(r);
  renderLocPos(r);
  Panels.load(r).then(() => { renderHead(r); renderOverview(r); flashIfUpdated(r); });
}

function renderHead(r) {
  const s = r.summary, p = r.position, c0 = r.casualties[0], resp = Panels.state.response;
  const respFor = resp && resp.report_id === r.id ? resp : null;
  const posTxt = !p ? "–" : p.state === "ambiguous" ? areasTxt(p) : `±${Math.round(p.radius_m)} m`;
  const posCls = !p ? "" : p.state === "confirmed" ? "ok" : "warn";
  const mob = c0 && c0.mobility;
  const mobCls = !mob ? "" : mob.conflict ? "bad" : { walks: "ok", assisted: "warn", litter: "bad", trapped: "bad", unknown: "" }[mob.state];
  const tq = s.tq_ms;
  const tqCls = tq ? { w0: "", w1: "warn", w2: "bad", w3: "bad" }[tqClass(now() - tq)] : "";
  const alert = (r.alerts || []).slice(-1).map((a) => `<span class="alert" title="sound cue only">⚠ ${esc(a.class.replace(/_/g, " "))}</span>`).join("");
  $("head").innerHTML = `
    <h2>${esc(r.callsign || r.id)}</h2>${s.count ? `<span class="pbadge p${s.rank}">P${s.rank}</span>` : ""}
    <div class="kpi ${posCls}"><span>Position</span><b>${posTxt}</b></div>
    <div class="kpi ${tqCls}"><span>Tourniquet</span><b ${tq ? `data-tqk="${tq}"` : ""}>${tq ? fmtElapsed(now() - tq) : "–"}</b></div>
    <div class="kpi ${mobCls}" title="${esc(mob ? (mob.conflict ? "⚠ " + mob.conflict + ": stretcher planned. " : "") + mob.source + ": " + mob.evidence.join("; ") : "")}">
      <span>Mobility${mob && mob.source !== "said" ? " (inf.)" : ""}</span><b>${mob ? (mob.conflict ? "⚠ " + SHORT[mob.plan] : SHORT[mob.state]) : "–"}</b></div>
    <div class="kpi"><span>Send</span><b>${respFor ? respFor.team.total : "…"}</b></div>
    ${r.outside ? `<div class="kpi bad" title="Said a town outside the mapped area: no position is guessed"><span>Outside map</span><b>${esc(r.outside)}</b></div>` : ""}
    ${worseKpi(r)}
    ${routeKpi(r)}
    ${stressKpi(r.stress)}
    <div class="ask">${r.question ? `<b>Asking:</b> ${esc(r.question.text)}${r.question.goal_text ? `<small class="goal">${esc(r.question.goal_text)}</small>` : ""}` : `<b>Read-back:</b> ${esc(r.readback)}`}</div>
    ${alert}
    <div class="actions">${r.truth && r.question ? `<button id="autoBtn" title="Rehearsal: answer as the simulated soldier">Auto-answer</button>` : ""}
      ${r.truth ? `<button id="listenBtn" class="ghost" title="Rehearsal: fake Listen clip">Listen (sim)</button>` : ""}
      ${guideButtons(r)}
      <button id="evacBtn" class="ghost">${r.evacuated ? "Undo evac" : "Evacuated"}</button></div>`;
  document.querySelectorAll("[data-guide]").forEach((b) => (b.onclick = async () => {
    b.disabled = true;
    await fetch(`/api/report/${r.id}/guide`, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: b.dataset.guide }) });
  }));
  $("evacBtn").onclick = () => fetch(`/api/report/${r.id}/evacuated`, { method: "POST" });
  if ($("autoBtn")) $("autoBtn").onclick = async (e) => { e.target.disabled = true; e.target.textContent = "answering…"; await fetch(`/api/report/${r.id}/auto_answer`, { method: "POST" }); };
  if ($("listenBtn")) $("listenBtn").onclick = async (e) => { e.target.disabled = true; e.target.textContent = "listening…"; await fetch(`/api/report/${r.id}/simulate_listen`, { method: "POST" }); };
}

function routeKpi(r) {
  const g = r.guide, d = r.dispatch;
  if (r.at_ccp) return `<div class="kpi ok"><span>Route</span><b>at CCP</b></div>`;
  if (g && g.state === "active") return `<div class="kpi" title="${esc(g.instruction || "")}"><span>To CCP</span><b>${fmtDist(g.left_m)} · ${fmtMin(g.eta_s)}</b></div>`;
  if (g && g.state === "lost") return `<div class="kpi warn"><span>To CCP</span><b>lost</b></div>`;
  if (d) return `<div class="kpi warn" title="CCP -> casualty, away from the danger zones"><span>Medic route</span><b>${fmtDist(d.length_m)} · ${fmtMin(d.eta_out_s)}</b></div>`;
  return "";
}
function guideButtons(r) {
  const g = r.guide;
  const plan = r.casualties.map((c) => c.mobility && c.mobility.plan);
  if (r.evacuated || r.at_ccp || !r.position || plan.includes("litter") || plan.includes("trapped")) return "";
  if (g && g.state === "active") return `<button data-guide="reached" class="ghost" title="The walker reached the end of this leg">Reached</button>
      <button data-guide="arrived" class="ghost">At CCP</button><button data-guide="stop" class="ghost">Stop guiding</button>`;
  return `<button data-guide="start" title="Plan a walking route to the CCP, away from the danger zones, and guide them by voice">Guide to CCP</button>`;
}
// ---------------------------------------------------------------- heart rate panel
// Right of the graph tile. Measured from a chest recording (field page: Pulse), never from
// the voice. The heart beats at the measured rate; grey when nothing has been measured.
const HEART_PATH = "M50 88 C20 66 4 48 4 30 C4 16 15 6 28 6 C38 6 46 12 50 20 C54 12 62 6 72 6 C85 6 96 16 96 30 C96 48 80 66 50 88 Z";
function renderHeart(r) {
  const el = $("heart");
  if (!el) return;
  const v = (r && r.vitals) || [];
  const last = v[v.length - 1];
  const fresh = last && now() - last.ms < 15 * 60000;
  const stress = r && r.stress && r.stress.level !== "unknown" ? r.stress.level : null;
  const band = (b) => b < 50 ? ["slow", "slow"] : b <= 100 ? ["normal", "normal"] : b <= 120 ? ["fast", "fast"] : b <= 140 ? ["shock", "shock range"] : ["shock", "severe"];
  if (!last || !last.bpm) {
    el.className = "heart";
    el.style.removeProperty("--beat");
    el.innerHTML = `<div class="hlabel">Heart rate</div><svg class="hicon" viewBox="0 0 100 92"><path d="${HEART_PATH}"/></svg>
      <div class="bpm">–</div><div class="hctx">Not measured.<br>Field phone: <b>🫀 Pulse</b>, microphone pressed on the chest, 10 s.</div>
      ${stress ? `<div class="hctx">Voice stress: <b>${esc(stress)}</b> (not a heart rate)</div>` : ""}
      ${r && r.truth && r.casualties.length ? `<button id="pulseSim" class="ghost" style="margin-top:6px">Pulse (sim)</button>` : ""}`;
  } else {
    const [cls, txt] = band(last.bpm);
    const sure = last.ok;
    el.className = "heart " + (fresh ? (sure ? "live" : "live unsure") : "stale");
    el.style.setProperty("--beat", (60 / last.bpm).toFixed(3) + "s");
    const pts = v.filter((x) => x.bpm).slice(-12);
    let spark = "";
    if (pts.length > 1) {
      const lo = Math.min(50, ...pts.map((p) => p.bpm)), hi = Math.max(150, ...pts.map((p) => p.bpm));
      const xy = pts.map((p, i) => `${(i / (pts.length - 1)) * 170 + 5},${30 - ((p.bpm - lo) / (hi - lo)) * 26}`).join(" ");
      const y120 = 30 - ((120 - lo) / (hi - lo)) * 26;
      spark = `<svg class="spark" viewBox="0 0 180 34"><line x1="0" x2="180" y1="${y120}" y2="${y120}" stroke="#e5484d" stroke-dasharray="3 3" opacity=".5"/>
        <polyline points="${xy}" fill="none" stroke="#e6ece9" stroke-width="1.5"/></svg>`;
    }
    el.innerHTML = `<div class="hlabel">Heart rate</div><svg class="hicon" viewBox="0 0 100 92"><path d="${HEART_PATH}"/></svg>
      <div class="bpm">${sure ? "" : "~"}${last.bpm}<small> bpm</small></div>
      <div class="hband ${cls}">${txt}${last.regular === false ? " · irregular?" : ""}</div>
      <div class="hctx">${esc(last.source)} · ${ago(last.ms)}${sure ? "" : "<br>unclear: press firmly, repeat"}${fresh ? "" : "<br>old reading: measure again"}</div>
      ${spark}
      ${stress ? `<div class="hctx">Voice stress: <b>${esc(stress)}</b></div>` : ""}
      ${r && r.truth ? `<button id="pulseSim" class="ghost" style="margin-top:4px">Pulse (sim)</button>` : ""}`;
  }
  const b = $("pulseSim");
  if (b) b.onclick = async (e) => { e.target.disabled = true; e.target.textContent = "measuring…"; await fetch(`/api/report/${r.id}/simulate_pulse`, { method: "POST" }); };
}

// ---------------------------------------------------------------- casualty condition
// backend/condition.py: MARCH states, distress, overall state, threats with time windows.
// Decision support: the windows are textbook orders of magnitude, to check with a medic.
const STATE_CLS = { stable: "ok", serious: "warn", critical: "bad", "very critical": "bad" };
function fmtLeft(ms) {
  if (ms <= 0) return "now";
  const m = Math.floor(ms / 60000);
  return m >= 90 ? `${Math.round(m / 60)} h` : m >= 1 ? `${m} min` : `${Math.ceil(ms / 1000)} s`;
}
function worseText(at) {        // [low, high] epoch ms -> "≈ 3–10 min"
  const lo = at[0] - now(), hi = at[1] - now();
  if (hi <= 0) return "overdue";
  return lo <= 0 ? `now – ${fmtLeft(hi)}` : `${fmtLeft(lo)} – ${fmtLeft(hi)}`;
}
function condLine(c) {
  if (!c) return "";
  const w = c.worse_in;
  return `<div class="meta cline"><span class="cst ${STATE_CLS[c.state]}">${esc(c.state)}</span>${w ? ` · worse in <b data-dl="${w.at_ms.join(",")}">${worseText(w.at_ms)}</b>` : ""}</div>`;
}
function worseKpi(r) {
  const cs = r.casualties.map((c) => c.condition).filter((c) => c && c.worse_in);
  if (!cs.length) return `<div class="kpi" title="Needs casualty details"><span>Worse in</span><b>–</b></div>`;
  const c = cs.reduce((a, b) => (a.worse_in.at_ms[0] <= b.worse_in.at_ms[0] ? a : b));
  const left = c.worse_in.at_ms[0] - now();
  return `<div class="kpi ${left < 10 * 60000 ? "bad" : left < 30 * 60000 ? "warn" : ""}" title="${esc(`${c.worse_in.threat} · helps: ${c.worse_in.helps} · decision support, windows to check with a medic`)}">
    <span>Worse in</span><b data-dl="${c.worse_in.at_ms.join(",")}">${worseText(c.worse_in.at_ms)}</b></div>`;
}
function condPanel(c, n) {
  if (!c) return "";
  const M = { M: "Massive bleeding", A: "Airway", R: "Breathing", C: "Circulation / shock", H: "Head / hypothermia" };
  const bad = (v) => /NOT|RISK|PROBLEM|SHOCK|massive|head/.test(v) ? "bad" : /unknown/.test(v) ? "unk" : "ok";
  const march = Object.entries(c.march).map(([k, v]) => `<div class="m ${bad(v)}"><b>${k}</b><span>${M[k]}</span><em>${esc(v)}</em></div>`).join("");
  const threats = c.threats.map((t) => `<li class="${t.status}"><b>${t.march}</b> ${esc(t.label)}
      <span class="tleft" data-dl="${t.at_ms.join(",")}">${worseText(t.at_ms)}</span>
      <small>window ${t.window_min[0]}–${t.window_min[1]} min from ${esc(t.from)} · ${esc(t.helps)}</small></li>`).join("");
  const w = c.worse_in;
  const sus = c.suspect.length ? `<div class="crow"><b>Hidden injuries to check</b> ${c.suspect.map((s) => esc(s[1])).join(", ")}</div>` : "";
  return `<div class="cond ${STATE_CLS[c.state]}">
    <div class="chead"><span class="cstate">${esc(c.state)}</span><span class="cscore">${c.score}/100</span>
      ${n ? `<span class="meta">casualty ${n}</span>` : ""}<span class="meta right">${c.self_report ? "self-report · " : ""}decision support</span></div>
    ${w ? `<div class="cworse">Gets worse in <b data-dl="${w.at_ms.join(",")}">${worseText(w.at_ms)}</b> · ${esc(w.threat)}<small>helps: ${esc(w.helps)}</small></div>`
        : `<div class="cworse muted">No time-critical threat from what was said so far.</div>`}
    <div class="march">${march}</div>
    <div class="crow"><b>Responds</b> ${esc(c.avpu ? c.avpu + " · " + c.avpu_label : "unknown")}
      <b>Distress</b> <span class="dist ${c.distress}">${esc(c.distress)}</span>${c.distress_from.length ? ` <small>(${esc(c.distress_from.join("; "))})</small>` : ""}</div>
    <div class="crow"><b>How</b> ${esc(c.mechanism || "not said yet")} <b>Since injury</b> ${c.since_injury_min} min <small>(clock from ${esc(c.injury_basis)})</small></div>
    ${sus}
    ${threats ? `<ul class="threats">${threats}</ul>` : ""}
  </div>`;
}

// How stressed the speaker sounds (backend/stress.py): changes how we ask, never the priority.
function stressKpi(s) {
  if (!s || !s.level || s.level === "unknown") return `<div class="kpi" title="Needs a push-to-talk clip"><span>Voice stress</span><b>–</b></div>`;
  const cls = { low: "ok", elevated: "warn", high: "bad" }[s.level] || "";
  const why = (s.cues || []).filter((c) => c.z > 0.5).map((c) => `${c.cue} (${c.value})`).join(", ") || "nothing stands out";
  return `<div class="kpi ${cls}" title="${esc(`${s.source}, confidence ${s.confidence}. Strong cues: ${why}. Adapts the questions: fewer, simpler, shorter when high.`)}">
    <span>Voice stress</span><b>${s.level}</b></div>`;
}

function renderOverview(r) {
  renderHeart(r);
  const resp = Panels.state.response && Panels.state.response.report_id === r.id ? Panels.state.response : null;
  $("cardMeta").textContent = `${r.callsign || r.id}${r.summary.count > 1 ? " · ×" + r.summary.count : ""}`;
  const mist = r.casualties.map((c, i) => `<div class="mist">
      <b>M</b><span>${esc(c.mist.M)} ${r.casualties.length > 1 ? `(#${i + 1})` : ""} ${c.count > 1 ? `×${c.count}` : ""}
        <span class="pbadge p${{ urgent: 1, priority: 2, routine: 3 }[c.priority]}" style="margin-left:4px">${c.priority}</span></span>
      <b>I</b><span>${esc(c.mist.I)}</span><b>S</b><span>${esc(c.mist.S)}</span><b>T</b><span>${esc(c.mist.T)}</span></div>`).join("");
  let plan = "";
  if (resp && resp.casualties) {
    const t = resp.team;
    plan = `<div class="label">Plan</div><div class="plan card"><div class="big">${t.total}</div>
      <div><b style="font-size:12px">to send</b> <span class="meta">${t.bearers} bearers · ${t.medics} medic${t.medics === 1 ? "" : "s"}${t.escorts ? ` · ${t.escorts} escort` : ""}${t.extrication ? ` · ${t.extrication} extraction` : ""}</span>
      <ul>${t.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div></div>`;
  }
  // What each report or clip changed for this casualty (backend state._log_changes), newest first.
  const chg = (r.changes || []).slice().reverse();
  const updates = chg.length ? `<div class="label">Updates <span class="meta">· every report and clip re-estimates everything</span></div>
    <div class="changes">${chg.slice(0, 4).map((c, i) => `<div class="chg ${i === 0 && now() - c.ms < 120000 ? "new" : ""}">
      <span class="via">${esc(c.via)}</span><span class="when">${ago(c.ms)}</span> ${c.via === "voice" ? `“${esc(c.what)}”` : esc(c.what)}
      <ul>${c.items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`).join("")}</div>` : "";
  const qa = r.asked.map((q) => `<div>${esc(q.text)}${q.goal_text ? `<div class="goal">${esc(q.goal_text)}</div>` : ""}${q.answer != null ? `<span class="ans">→ ${esc(q.answer)}</span>` : `<span class="pending">waiting for answer…</span>`}
      ${q.gain_bits ? `<span class="meta"> · ${q.gain_bits} bits</span>` : ""}${q.load ? `<span class="meta"> · effort ${q.load}${q.stress && q.stress !== "unknown" ? `, speaker ${q.stress}` : ""}</span>` : ""}</div>`).join("");
  const tx = r.transcripts.slice().reverse().map((t) => `<div><span class="src">${esc(t.via)}/${esc(t.source)}</span>${esc(t.text)}</div>`).join("");
  const cond = r.casualties.map((c, i) => condPanel(c.condition, r.casualties.length > 1 ? i + 1 : null)).join("");
  $("overview").innerHTML = `${cond}${mist || `<div class="empty">No casualty details yet.</div>`}${updates}${plan}
    ${qa ? `<div class="label">Questions asked</div><div class="qa">${qa}</div>` : ""}
    <details ${r.transcripts.length <= 1 ? "open" : ""}><summary>Transcripts (${r.transcripts.length})</summary><div class="tx">${tx}</div></details>
    ${r.packet ? `<div class="packet">${esc(r.packet.text)} · <b>${r.packet.bytes} bytes</b></div>` : ""}`;
}

function renderLocPos(r) {
  const p = r.position;
  if (!p) { $("locMeta").textContent = "no position yet"; $("locPos").innerHTML = `<div class="muted">No position yet: landmarks with clock directions, the sun, or a Listen clip will give one.</div>`; return; }
  const cls = p.state === "confirmed" ? "ok" : p.state === "ambiguous" ? "amb" : "rough";
  const txt = p.state === "ambiguous" ? "possible " + areasTxt(p) : `± ${Math.round(p.radius_m)} m`;
  let err = "";
  if (r.truth) {
    const dy = (r.truth.lat - p.lat) * 110540, dx = (r.truth.lon - p.lon) * 111320 * Math.cos((p.lat * Math.PI) / 180);
    err = ` · <span style="color:#33e1ff">true error ${Math.round(Math.hypot(dx, dy))} m</span>`;
  }
  const ev = r.evidence ? Object.entries(r.evidence).map(([k, v]) => `${k} ${v}`).join(" · ") : "";
  $("locMeta").textContent = `${txt} · ${p.state}`;
  $("locPos").innerHTML = `<span class="big ${cls}">${txt}</span> <span class="meta">${p.state}</span><br>
    <span class="meta">${p.lat.toFixed(5)}, ${p.lon.toFixed(5)} · heading ~${Math.round(p.heading_deg)}°${err}</span>
    ${ev ? `<div class="meta">evidence: ${esc(ev)}</div>` : ""}`;
}

// Candidate areas on the main map; fly there only when the user picks another area.
let lastPick = {};
Panels.onCandidates = (cs, pick) => {
  candLayer.clearLayers();
  cs.forEach((c, i) => {
    const on = i === pick;
    L.circle([c.lat, c.lon], { radius: c.radius_m, color: on ? "#e8c547" : "#8b9a94", weight: on ? 2.5 : 1, dashArray: on ? null : "4 4",
                               fillOpacity: on ? 0.15 : 0.04, interactive: false }).addTo(candLayer);
    L.marker([c.lat, c.lon], { interactive: false, icon: L.divIcon({ className: "", html: `<div class="blob-label" style="${on ? "" : "background:#8b9a94"}">${c.label}</div>`, iconSize: [22, 22], iconAnchor: [11, 11] }) }).addTo(candLayer);
    if (c.spot && on) L.circleMarker([c.spot.lat, c.spot.lon], { radius: 5, color: "#33e1ff", weight: 2, fillOpacity: 0.9 })
      .bindTooltip(`area ${c.label}: spot that best fits the echoes and noise level`).addTo(candLayer);
  });
  const prev = lastPick[selected];
  lastPick[selected] = pick;
  if (cs[pick] && prev !== undefined && prev !== pick) map.flyTo([cs[pick].lat, cs[pick].lon], Math.max(map.getZoom(), 16), { duration: 0.6 });
};

function select(id, auto = false, zoom = false) {
  const changed = id !== selected;
  selected = id;
  if (!state) return;
  const r = state.reports.find((x) => x.id === id);
  if ((changed || zoom) && r && r.position && r.position.blobs.length) {
    map.fitBounds(L.latLngBounds(r.position.blobs.flatMap((b) => ellipse(b))), { padding: [60, 60], maxZoom: 17 });
  }
  if (!auto) render();
}

// ---------------------------------------------------------------- enlarge a tile
function enlarge(tile) {
  const open = document.querySelector(".tile.big");
  if (open) { open.classList.remove("big"); open.querySelector(".max").textContent = "⤢"; }
  const show = tile && tile !== open;
  if (show) { tile.classList.add("big"); tile.querySelector(".max").textContent = "✕"; }
  $("backdrop").hidden = !show;
  // Canvases, the map and the 3D view must redraw at their new size.
  requestAnimationFrame(() => { map.invalidateSize(); Panels.redraw(); window.dispatchEvent(new Event("resize")); });
}
document.querySelectorAll(".tile .max").forEach((b) => (b.onclick = () => enlarge(b.closest(".tile"))));
document.querySelectorAll(".tile h3").forEach((h) => (h.ondblclick = () => enlarge(h.closest(".tile"))));
$("backdrop").onclick = () => enlarge(null);
document.addEventListener("keydown", (e) => { if (e.key === "Escape") enlarge(null); });

// ---------------------------------------------------------------- timers
setInterval(() => {
  $("clock").textContent = new Date(now()).toLocaleTimeString("fr-FR");
  document.querySelectorAll("[data-tq]").forEach((el) => {
    const ms = now() - Number(el.dataset.tq);
    if (el.classList.contains("tag")) el.textContent = "TQ " + fmtElapsed(ms);
    else { el.className = "tq " + tqClass(ms); el.innerHTML = fmtElapsed(ms) + "<small>TQ</small>"; }
  });
  document.querySelectorAll("[data-tqk]").forEach((el) => (el.textContent = fmtElapsed(now() - Number(el.dataset.tqk))));
  document.querySelectorAll("[data-dl]").forEach((el) => (el.textContent = worseText(el.dataset.dl.split(",").map(Number))));
}, 1000);

setInterval(() => { if (state) drawDanger(); }, 15000);   // zones fade as reports age

// ---------------------------------------------------------------- websocket
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { $("status").textContent = "live"; $("status").className = "sub live"; };
  ws.onmessage = (e) => { state = JSON.parse(e.data); offset = state.server_ms - Date.now(); render(); };
  ws.onclose = () => { $("status").textContent = "reconnecting…"; $("status").className = "sub"; setTimeout(connect, 1500); };
}
connect();

// ---------------------------------------------------------------- tools
function setMode(m) {
  mode = mode === m ? null : m;
  $("ccpBtn").classList.toggle("on", mode === "ccp");
  $("simBtn").classList.toggle("on", mode === "sim");
  $("hint").textContent = mode === "ccp" ? "Click the map to place the casualty collection point."
    : mode === "sim" ? "Click where the simulated soldier stands (cyan + = truth). Click again for more; press the button again to stop." : "";
  map.getContainer().style.cursor = mode ? "crosshair" : "";
}
$("ccpBtn").onclick = () => setMode("ccp");
$("simBtn").onclick = () => setMode("sim");
$("lmBtn").onclick = () => {
  const on = map.hasLayer(lmLayer);
  on ? map.removeLayer(lmLayer) : map.addLayer(lmLayer);
  $("lmBtn").classList.toggle("on", !on);
};
$("resetBtn").onclick = () => { if (confirm("Clear all reports?")) fetch("/api/reset", { method: "POST" }); };
map.on("click", async (e) => {
  if (mode === "ccp") {
    await fetch("/api/ccp", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: e.latlng.lat, lon: e.latlng.lng }) });
    setMode("ccp");
  } else if (mode === "sim") {
    $("hint").textContent = "simulating…";
    const r = await fetch("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: e.latlng.lat, lon: e.latlng.lng }) });
    const d = await r.json();
    lastManual = 0;
    if (d.report_id) fetch(`/api/report/${d.report_id}/simulate_listen`, { method: "POST" });   // so Sound has a clip
    $("hint").textContent = d.readback || d.error || "";
  }
});

// Deep links: /map#body, /map#graph, /map#response, /map#sound, /map#location, /map#map (handy for the demo video).
(function fromHash() {
  const id = { list: "tList", card: "tCard", map: "tMap", body: "tBody", location: "tLoc", sound: "tSound", response: "tResp", graph: "tGraph" }[location.hash.slice(1)];
  if (id) setTimeout(() => enlarge($(id)), 300);
})();
