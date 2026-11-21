// Coordinator page: live map + evacuation list, fed by the /ws websocket.
const $ = (id) => document.getElementById(id);
const COLORS = { 1: "#e5484d", 2: "#f0a33a", 3: "#4cc38a", 9: "#8b9a94" };
let state = null, offset = 0, selected = null, lastManual = 0, lastSeenUpdate = 0, mode = null;

// ---------------------------------------------------------------- map setup
const map = L.map("map", { zoomControl: true }).setView([48.8435, 2.4355], 15);
const OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATTR = "&copy; OpenStreetMap contributors";
const dark = L.tileLayer(OSM_URL, { maxZoom: 19, attribution: OSM_ATTR, className: "dark-tiles" }).addTo(map);
const osm = L.tileLayer(OSM_URL, { maxZoom: 19, attribution: OSM_ATTR });
L.control.layers({ "Dark": dark, "OpenStreetMap": osm }, {}, { position: "topleft" }).addTo(map);
L.control.scale({ imperial: false }).addTo(map);
// Landmark names only when zoomed in (keep / castle always).
function zoomClass() { map.getContainer().classList.toggle("far", map.getZoom() < 16); }
map.on("zoomend", zoomClass); zoomClass();

const heatLayer = L.layerGroup().addTo(map);
const reportLayer = L.layerGroup().addTo(map);
const lmLayer = L.layerGroup().addTo(map);
let ccpMarker = null, heatKey = null;

// Landmarks we can match against (small labels).
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
function fmtElapsed(ms) {
  const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}
function tqClass(ms) {
  const m = ms / 60000, w = (state && state.tq_warn_min) || [60, 90, 120];
  return m >= w[2] ? "w3" : m >= w[1] ? "w2" : m >= w[0] ? "w1" : "w0";
}
function fmtDist(d) { return d == null ? "" : d < 1000 ? `${Math.round(d / 10) * 10} m` : `${(d / 1000).toFixed(1)} km`; }

// 2-sigma ellipse polygon around a blob.
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

// Posterior heat map -> image overlay.
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
function drawHeat(rep) {
  const key = rep ? rep.id + ":" + rep.updated_ms : null;
  if (key === heatKey) return;
  heatKey = key;
  heatLayer.clearLayers();
  if (!rep || !rep.heat) return;
  const h = rep.heat, raw = atob(h.data);
  const c = document.createElement("canvas");
  c.width = h.w; c.height = h.h;
  const ctx = c.getContext("2d"), img = ctx.createImageData(h.w, h.h);
  for (let i = 0; i < raw.length; i++) {
    const v = raw.charCodeAt(i) / 255;
    if (v < 0.03) continue;
    const [r, g, b, a] = ramp(v);
    img.data[i * 4] = r; img.data[i * 4 + 1] = g; img.data[i * 4 + 2] = b; img.data[i * 4 + 3] = a * 255;
  }
  ctx.putImageData(img, 0, 0);
  const bd = h.bounds;
  L.imageOverlay(c.toDataURL(), [[bd.south, bd.west], [bd.north, bd.east]], { opacity: 0.9 }).addTo(heatLayer);
}

// ---------------------------------------------------------------- rendering
function render() {
  if (!state) return;
  const reps = Object.fromEntries(state.reports.map((r) => [r.id, r]));

  // Follow the latest update unless the user clicked something recently.
  const newest = state.reports.reduce((a, r) => (!a || r.updated_ms > a.updated_ms ? r : a), null);
  if (newest && newest.updated_ms > lastSeenUpdate) {
    lastSeenUpdate = newest.updated_ms;
    if (Date.now() - lastManual > 20000 || !selected) select(newest.id, true);
  }
  if (selected && !reps[selected]) selected = null;

  // CCP
  const ccp = state.ccp;
  if (!ccpMarker) ccpMarker = L.marker([ccp.lat, ccp.lon], { icon: L.divIcon({ className: "", html: `<span class="ccp">✚ CCP</span>`, iconSize: null }) }).addTo(map);
  ccpMarker.setLatLng([ccp.lat, ccp.lon]);

  // Pins + ellipses
  reportLayer.clearLayers();
  for (const r of state.reports) {
    const p = r.position;
    if (!p || p.lat == null) continue;
    const col = COLORS[r.summary.rank] || COLORS[9];
    const sel = r.id === selected;
    p.blobs.forEach((b, i) => {
      L.polygon(ellipse(b), { color: col, weight: sel ? 2.5 : 1.5, opacity: sel ? 1 : 0.6, dashArray: i ? "5 6" : null,
        fillColor: col, fillOpacity: sel ? 0.06 : 0.03, interactive: false }).addTo(reportLayer);
      if (i) L.circleMarker([b.lat, b.lon], { radius: 4, color: col, weight: 2, fillOpacity: 0.3, interactive: false }).addTo(reportLayer);
    });
    const tag = r.summary.tq_ms ? `<span class="tag" data-tq="${r.summary.tq_ms}">TQ ${fmtElapsed(now() - r.summary.tq_ms)}</span>`
                                : `<span class="tag">${esc(r.callsign || r.id)}</span>`;
    const label = r.summary.count ? `P${r.summary.rank}` : "?";
    const m = L.marker([p.lat, p.lon], { zIndexOffset: sel ? 1000 : 0, icon: L.divIcon({ className: "", iconSize: [40, 50], iconAnchor: [20, 18],
      html: `<div class="pin"><div class="dot" style="background:${col}">${label}</div>${tag}</div>` }) });
    m.on("click", () => { lastManual = Date.now(); select(r.id); });
    m.addTo(reportLayer);
    if (r.truth) {
      L.marker([r.truth.lat, r.truth.lon], { interactive: false, icon: L.divIcon({ className: "", html: `<span class="truth">+</span>`, iconSize: null }) }).addTo(reportLayer);
      L.polyline([[r.truth.lat, r.truth.lon], [p.lat, p.lon]], { color: "#33e1ff", weight: 1, dashArray: "2 4", interactive: false }).addTo(reportLayer);
    }
  }
  drawHeat(reps[selected]);
  renderList(reps);
  renderDetail(reps[selected]);
  ScenePanel.show(reps[selected]);
}

function renderList(reps) {
  const live = state.order.map((id) => reps[id]);
  const others = state.reports.filter((r) => !state.order.includes(r.id));
  $("count").textContent = live.length ? `· ${live.length}` : "";
  if (!live.length && !others.length) { $("list").innerHTML = `<div class="empty">No casualties reported yet.</div>`; return; }
  const row = (r, rank) => {
    const s = r.summary, tq = s.tq_ms;
    const pos = r.position ? `± ${Math.round(r.position.radius_m)} m` : "no position";
    const c0 = r.casualties[0];
    const what = c0 ? [c0.mechanism, (c0.injuries || [])[0]].filter(Boolean).join(" · ") : "awaiting details";
    return `<div class="item ${r.id === selected ? "sel" : ""} ${r.evacuated ? "evac" : ""}" data-id="${r.id}">
      <div class="rank">${rank ?? "–"}</div>
      <div><div class="top">${s.count ? `<span class="pbadge p${s.rank}">P${s.rank}</span>` : ""}
        <span class="name">${esc(r.callsign || r.id)}</span>${s.count > 1 ? `<span class="meta">×${s.count}</span>` : ""}</div>
        <div class="meta">${esc(what)}${c0 && c0.mobility ? ` · <span class="mob ${c0.mobility.state}">${esc(c0.mobility.label.split(":")[0])}</span>` : ""}</div>
        <div class="meta">${pos}${r.distance_ccp != null ? " · " + fmtDist(r.distance_ccp) + " to CCP" : ""}${r.question ? " · asking…" : ""}</div></div>
      <div class="tq ${tq ? tqClass(now() - tq) : ""}" ${tq ? `data-tq="${tq}"` : ""}>${tq ? fmtElapsed(now() - tq) + "<small>TOURNIQUET</small>" : ""}</div>
    </div>`;
  };
  $("list").innerHTML = live.map((r, i) => row(r, i + 1)).join("") + others.map((r) => row(r, null)).join("");
  document.querySelectorAll(".item").forEach((el) => el.addEventListener("click", () => { lastManual = Date.now(); select(el.dataset.id, false, true); }));
}

function renderDetail(r) {
  const d = $("detail");
  if (!r) { d.hidden = true; return; }
  d.hidden = false;
  const p = r.position, s = r.summary;
  let posHtml = `<div class="pos">No position yet.</div>`;
  if (p) {
    const cls = p.state === "confirmed" ? "ok" : p.state === "ambiguous" ? "amb" : "rough";
    const txt = p.state === "ambiguous" ? `${p.blobs.filter((b) => b.mass >= 0.12).length} possible areas` : `± ${Math.round(p.radius_m)} m`;
    let err = "";
    if (r.truth) {
      const dy = (r.truth.lat - p.lat) * 110540, dx = (r.truth.lon - p.lon) * 111320 * Math.cos((p.lat * Math.PI) / 180);
      err = ` · <span style="color:#33e1ff">true error ${Math.round(Math.hypot(dx, dy))} m</span>`;
    }
    posHtml = `<div class="pos"><span class="big ${cls}">${txt}</span> <span class="meta">${p.state}</span><br>
      <span class="meta">${p.lat.toFixed(5)}, ${p.lon.toFixed(5)} · heading ~${Math.round(p.heading_deg)}°${err}</span></div>`;
  }
  const mist = r.casualties.map((c, i) => `<div class="mist">
      <b>M</b><span>${esc(c.mist.M)} ${r.casualties.length > 1 ? `(#${i + 1})` : ""} ${c.count > 1 ? `×${c.count}` : ""}
        <span class="pbadge p${{ urgent: 1, priority: 2, routine: 3 }[c.priority]}" style="margin-left:6px">${c.priority}</span>
        ${c.mobility ? `<span class="mob ${c.mobility.state}" title="${esc(c.mobility.source + ": " + c.mobility.evidence.join("; "))}">${esc(c.mobility.label)}${c.mobility.source === "said" ? "" : " (inferred)"}</span>` : ""}</span>
      <b>I</b><span>${esc(c.mist.I)}</span><b>S</b><span>${esc(c.mist.S)}</span><b>T</b><span>${esc(c.mist.T)}</span></div>`).join("");
  const qa = r.asked.map((q) => `<div>${esc(q.text)}<br>${q.answer != null ? `<span class="ans">→ ${esc(q.answer)}</span>` : `<span class="pending">waiting for answer…</span>`}
      ${q.gain_bits ? `<span class="meta"> · ${q.gain_bits} bits</span>` : ""}</div>`).join("");
  const tx = r.transcripts.slice().reverse().map((t) => `<div><span class="src">${esc(t.via)}/${esc(t.source)}</span>${esc(t.text)}</div>`).join("");
  const ac = acousticHtml(r);
  const ev = r.evidence ? Object.entries(r.evidence).map(([k, v]) => `${k} ${v}`).join(" · ") : "";
  const alerts = (r.alerts || []).map((a) => `<div class="alert">⚠ ${esc(a.class.replace(/_/g, " "))} (score ${a.score}) · ${new Date(a.ms).toLocaleTimeString("fr-FR")}<br>
      <span class="meta">sound cue only, can be a door slam or a misclassification</span></div>`).join("");
  d.innerHTML = `<div class="dhead"><h2>${esc(r.callsign || r.id)} ${s.count ? `<span class="pbadge p${s.rank}">P${s.rank}</span>` : ""}</h2>
      <div class="btns">${r.truth && r.question ? `<button id="autoBtn">Auto-answer</button>` : ""}
      ${r.truth ? `<button id="listenBtn" class="ghost" title="Fake Listen clip drawn from the map truth">Simulate listen</button>` : ""}
      <button id="evacBtn" class="ghost">${r.evacuated ? "Undo evac" : "Evacuated"}</button></div></div>
    ${alerts}${posHtml}${ev ? `<div class="meta" style="margin:-4px 0 8px">evidence: ${esc(ev)}</div>` : ""}
    ${mist || `<div class="empty">No casualty details yet.</div>`}${ac}
    ${qa ? `<div class="label" style="margin-top:12px">Questions asked</div><div class="qa">${qa}</div>` : ""}
    <div class="label" style="margin-top:12px">Last read-back</div><div class="tx" style="color:var(--text)">${esc(r.readback)}</div>
    <div class="label" style="margin-top:12px">Transcripts</div><div class="tx">${tx}</div>
    ${r.packet ? `<div class="packet">${esc(r.packet.text)}<br><b>${r.packet.bytes} bytes</b> · fits a jammed / low-bandwidth link</div>` : ""}`;
  $("evacBtn").onclick = () => fetch(`/api/report/${r.id}/evacuated`, { method: "POST" });
  if ($("autoBtn")) $("autoBtn").onclick = async (e) => { e.target.disabled = true; e.target.textContent = "answering…";
    await fetch(`/api/report/${r.id}/auto_answer`, { method: "POST" }); };
  if ($("listenBtn")) $("listenBtn").onclick = async (e) => { e.target.disabled = true; e.target.textContent = "listening…";
    await fetch(`/api/report/${r.id}/simulate_listen`, { method: "POST" }); };
}

// Space & sound: what the microphone says about where the phone is.
const SPACE_NAMES = { indoor_small: "indoors · small room", indoor_large: "indoors · large hall",
                      outdoor_enclosed: "outdoors · between buildings", outdoor_open: "outdoors · open ground" };
function acousticHtml(r) {
  const list = r.acoustic || [];
  if (!list.length) return "";
  const a = list[list.length - 1], sp = a.space || {}, pr = sp.probe || {};
  const bars = sp.p && sp.strength >= 0.05
    ? Object.entries(sp.p).map(([k, v]) => `<div class="sbar"><span>${SPACE_NAMES[k]}</span>
      <i style="width:${Math.round(v * 100)}%"></i><b>${Math.round(v * 100)}%</b></div>`).join("")
    : `<div class="meta">no spatial clue in this clip (dry or too short, no usable echo)</div>`;
  const nums = [];
  if (sp.rt60_passive_s) nums.push(`reverb (voice/ambient) ${sp.rt60_passive_s} s`);
  if (pr.ok) {                        // a failed chirp's echo numbers mean nothing
    if (pr.rt60_s) nums.push(`reverb (chirp) ${pr.rt60_s} s`);
    if (pr.drr_db != null) nums.push(`DRR ${pr.drr_db} dB`);
    if (pr.nearest_wall_m) nums.push(`wall echo ${pr.nearest_wall_m} m${pr.wall_reliable ? "" : " (low confidence)"}`);
    if (pr.floor_or_ceiling_m) nums.push(`floor/ceiling ${pr.floor_or_ceiling_m} m`);
  }
  if (sp.room_size_m) nums.push(`room ~${sp.room_size_m[0]}–${sp.room_size_m[1]} m across`);
  if (pr.ok === false && pr.why) nums.push(`chirp failed: ${pr.why}`);
  const evs = (a.events || []).map((e) => `${e.class} ${e.score}`).join(" · ");
  const ctx = (a.context || []).map((e) => `${e.class} ${e.score}`).join(" · ");
  return `<div class="label" style="margin-top:12px">Space & sound <span class="meta">· ${esc(a.kind)} clip · ${esc(a.quality || "")}</span></div>
    <div class="acoustic">${bars}
      ${nums.length ? `<div class="meta">${esc(nums.join(" · "))}</div>` : ""}
      ${(sp.clues || []).length ? `<div class="meta">clues: ${esc(sp.clues.join("; "))}</div>` : ""}
      ${evs ? `<div class="meta">heard (raw scores): ${esc(evs)}</div>` : ""}
      ${ctx ? `<div class="meta">context only: ${esc(ctx)}</div>` : ""}
      ${(a.notes || []).length ? `<div class="meta">notes: ${esc(a.notes.join("; "))}</div>` : ""}
      ${a.used && a.used.length ? `<div class="meta">used for position: ${esc(a.used.join(", "))}</div>` : ""}</div>`;
}

function select(id, auto = false, zoom = false) {
  const changed = id !== selected;
  selected = id;
  if (!state) return;
  const r = state.reports.find((x) => x.id === id);
  if ((changed || zoom) && r && r.position && r.position.blobs.length) {
    const pts = r.position.blobs.flatMap((b) => ellipse(b));
    map.fitBounds(L.latLngBounds(pts), { padding: [60, 60], maxZoom: 17 });
  }
  if (!auto) render();
}

// Tick timers every second without re-rendering everything.
setInterval(() => {
  $("clock").textContent = new Date(now()).toLocaleTimeString("fr-FR");
  document.querySelectorAll("[data-tq]").forEach((el) => {
    const ms = now() - Number(el.dataset.tq);
    if (el.classList.contains("tag")) el.textContent = "TQ " + fmtElapsed(ms);
    else { el.className = "tq " + tqClass(ms); el.innerHTML = fmtElapsed(ms) + "<small>TOURNIQUET</small>"; }
  });
}, 1000);

// ---------------------------------------------------------------- websocket
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { $("status").textContent = "live"; $("status").className = "sub live"; };
  ws.onmessage = (e) => {
    state = JSON.parse(e.data);
    offset = state.server_ms - Date.now();
    render();
  };
  ws.onclose = () => { $("status").textContent = "reconnecting…"; $("status").className = "sub"; setTimeout(connect, 1500); };
}
connect();

// ---------------------------------------------------------------- tools
function setMode(m) {
  mode = mode === m ? null : m;
  $("ccpBtn").classList.toggle("on", mode === "ccp");
  $("simBtn").classList.toggle("on", mode === "sim");
  $("hint").textContent = mode === "ccp" ? "Click the map to place the casualty collection point."
    : mode === "sim" ? "Click where the simulated soldier stands (cyan + = truth). Click again for more." : "";
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
    $("hint").textContent = d.readback || d.error || "";
  }
});
