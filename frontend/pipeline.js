// Pipeline page: the three steps of one report, live.
//   1 Listen       spectrogram, sound classes over time, chirp echo, kind of space
//   2 Reconstruct  the guessed 3D scene (from the report only)
//   3 Match        real candidate areas: probability, map, real 3D scene, clue checks
// Report list comes from the /ws state; pictures from /api/report/{id}/viz and /scene.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let state = null, selId = null, loadedKey = null, viz = null, scene = null, pick = 0;
const view = { yaw: 0.45, elev: 0.6, auto: true };

// Rehearsal spots around the Château de Vincennes (streets, park edge, esplanade).
const SPOTS = [[48.8437, 2.4378], [48.8452, 2.4352], [48.8418, 2.4396], [48.8466, 2.4405],
               [48.8428, 2.4335], [48.8405, 2.4370], [48.8475, 2.4365]];

const GROUP_COLOR = { speech: "#8b9a94", rail: "#b9b2a6", traffic: "#f0a33a", bells: "#c9a0ff",
                      machinery: "#ff6b5a", nature: "#4cc38a", aircraft: "#5ac8ff", siren: "#e5484d", crowd: "#e6ece9" };
const SPACE_NAMES = { indoor_small: "indoors · small room", indoor_large: "indoors · large hall",
                      outdoor_enclosed: "outdoors · between buildings", outdoor_open: "outdoors · open ground" };

// ------------------------------------------------------------------ canvas helpers
function ctx(cv) {
  const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  g.font = "10px system-ui";
  return [g, w, h];
}
function emptyMsg(cv, text) {
  const [g, w, h] = ctx(cv);
  g.fillStyle = "#8b9a94"; g.font = "12px system-ui"; g.textAlign = "center";
  g.fillText(text, w / 2, h / 2); g.textAlign = "left";
}

// Inferno-like colour map, 256 entries.
const LUT = (() => {
  const stops = [[0, 0, 0, 4], [0.25, 87, 16, 110], [0.5, 188, 55, 84], [0.75, 249, 142, 9], [1, 252, 255, 164]];
  const out = [];
  for (let i = 0; i < 256; i++) {
    const v = i / 255;
    let k = 0; while (k < stops.length - 2 && v > stops[k + 1][0]) k++;
    const [a, b] = [stops[k], stops[k + 1]], t = (v - a[0]) / (b[0] - a[0]);
    out.push([0, 1, 2].map((j) => Math.round(a[j + 1] + t * (b[j + 1] - a[j + 1]))));
  }
  return out;
})();

const ML = 74;   // left margin shared by spectrogram and lanes, so time lines up
const mel = (f) => 2595 * Math.log10(1 + f / 700);

// ------------------------------------------------------------------ step 1
function drawSpec() {
  const cv = $("spec");
  if (!viz || !viz.spec) { emptyMsg(cv, "No audio yet: press Listen on the field phone, or Simulate listen."); $("specMeta").textContent = ""; return; }
  const sp = viz.spec;
  $("specMeta").textContent = `· ${viz.simulated ? "SIMULATED clip · " : ""}${viz.kind || ""} · ${sp.dur_s} s`;
  const [g, w, h] = ctx(cv);
  const pw = w - ML - 6, ph = h - 16;
  const raw = Uint8Array.from(atob(sp.data), (c) => c.charCodeAt(0));
  const off = document.createElement("canvas"); off.width = sp.w; off.height = sp.h;
  const img = off.getContext("2d").createImageData(sp.w, sp.h);
  raw.forEach((v, i) => { const c = LUT[v]; img.data.set([c[0], c[1], c[2], 255], i * 4); });
  off.getContext("2d").putImageData(img, 0, 0);
  g.imageSmoothingEnabled = true;
  g.drawImage(off, ML, 0, pw, ph);
  const X = (t) => ML + (t / sp.dur_s) * pw;

  // Frequency axis (mel).
  g.fillStyle = "#8b9a94"; g.strokeStyle = "rgba(255,255,255,.12)";
  const m0 = mel(sp.fmin), m1 = mel(sp.fmax);
  for (const f of [100, 250, 500, 1000, 2000, 4000, 8000]) {
    if (f > sp.fmax) continue;
    const y = ph * (1 - (mel(f) - m0) / (m1 - m0));
    g.fillText(f >= 1000 ? `${f / 1000} kHz` : `${f} Hz`, ML - 44, Math.max(y + 3, 9));
    g.beginPath(); g.moveTo(ML, y); g.lineTo(ML + pw, y); g.stroke();
  }
  // Time axis.
  for (let t = 0; t <= sp.dur_s; t += 1) { g.fillText(`${t}s`, X(t) - 4, h - 3); }
  // Chirp.
  if (viz.chirp) {
    const [a, b] = viz.chirp;
    g.strokeStyle = "#33e1ff"; g.setLineDash([4, 3]); g.strokeRect(X(a), 1, X(b) - X(a), ph - 2); g.setLineDash([]);
    g.fillStyle = "#33e1ff"; g.fillText("chirp", X(a) + 3, 12);
  }
  // Speech windows: hatched (not used to classify the environment).
  const tl = viz.timeline;
  if (tl) tl.t.forEach((t, i) => { if (!tl.kept[i]) hatch(g, X(t - 0.24), 0, X(t + 0.24) - X(t - 0.24), ph); });
}

function hatch(g, x, y, w, h) {
  g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
  g.strokeStyle = "rgba(230,236,233,.35)";
  for (let k = -h; k < w; k += 6) { g.beginPath(); g.moveTo(x + k, y + h); g.lineTo(x + k + h, y); g.stroke(); }
  g.restore();
}

function drawLanes() {
  const cv = $("lanes");
  const tl = viz && viz.timeline, dur = viz && viz.spec && viz.spec.dur_s;
  if (!tl || !dur) { ctx(cv); return; }
  const groups = Object.keys(tl.groups).filter((k) => k === "speech" || Math.max(...tl.groups[k]) >= 0.05);
  const allGeo = ["rail", "traffic", "bells", "machinery", "nature"];
  for (const k of allGeo) if (!groups.includes(k) && tl.groups[k]) groups.push(k);
  cv.style.height = `${Math.max(groups.length, 1) * 15 + 4}px`;
  const [g, w] = ctx(cv);
  const pw = w - ML - 6, X = (t) => ML + (t / dur) * pw;
  groups.forEach((k, r) => {
    const y = r * 15 + 2;
    g.fillStyle = "#1b2320"; g.fillRect(ML, y, pw, 12);
    const col = GROUP_COLOR[k] || "#e6ece9";
    tl.groups[k].forEach((v, i) => {
      if (v < 0.02) return;
      g.globalAlpha = Math.min(1, 0.15 + v); g.fillStyle = col;
      g.fillRect(X(tl.t[i] - 0.24), y, X(tl.t[i] + 0.24) - X(tl.t[i] - 0.24) - 1, 12);
    });
    g.globalAlpha = 1;
    const best = Math.max(...tl.groups[k]);
    g.fillStyle = best >= 0.1 ? col : "#5a6762"; g.fillText(`${k} ${best.toFixed(2)}`, 4, y + 10);
  });
}

function drawEcho() {
  const cv = $("echo");
  const eg = viz && viz.echogram;
  if (!eg) { emptyMsg(cv, viz ? "No chirp in this clip (Listen with the chirp on)." : ""); return; }
  const [g, w, h] = ctx(cv);
  const L = 30, B = 16, pw = w - L - 8, ph = h - B - 6, maxD = eg.db.length * eg.step_m;
  const X = (d) => L + (d / maxD) * pw, Y = (db) => 4 + ph * (Math.max(-60, Math.min(0, db)) / -60);
  // Floor / ground band: not a wall.
  g.fillStyle = "rgba(139,154,148,.12)"; g.fillRect(X(0.8), 4, X(1.8) - X(0.8), ph);
  g.fillStyle = "#8b9a94"; g.fillText("ground", X(0.8), ph + 2);
  g.strokeStyle = "rgba(255,255,255,.08)";
  for (const db of [0, -20, -40, -60]) { g.beginPath(); g.moveTo(L, Y(db)); g.lineTo(L + pw, Y(db)); g.stroke(); g.fillText(`${db}`, 4, Y(db) + 3); }
  for (let d = 0; d <= maxD; d += 5) g.fillText(`${d} m`, X(d) - 6, h - 3);
  g.beginPath(); eg.db.forEach((v, i) => { const x = X(i * eg.step_m), y = Y(v); i ? g.lineTo(x, y) : g.moveTo(x, y); });
  g.strokeStyle = "#33e1ff"; g.lineWidth = 1.2; g.stroke(); g.lineWidth = 1;
  if (viz.wall_m) {
    const x = X(viz.wall_m), col = viz.wall_reliable ? "#4cc38a" : "#f0a33a";
    g.strokeStyle = col; g.setLineDash([3, 3]); g.beginPath(); g.moveTo(x, 4); g.lineTo(x, ph + 4); g.stroke(); g.setLineDash([]);
    g.fillStyle = col; g.font = "600 11px system-ui";
    g.fillText(`facade ${viz.wall_m} m${viz.wall_reliable ? "" : " (low confidence)"}`, Math.min(x + 4, w - 150), 16);
  }
}

function renderSpace(rep) {
  const a = (rep.acoustic || [])[rep.acoustic.length - 1];
  if (!a) { $("space").innerHTML = `<div class="muted" style="font-size:13px">No clip analysed yet.</div>`; return; }
  const sp = a.space || {};
  const bars = sp.p ? Object.entries(sp.p).map(([k, v]) => `<div class="sbar"><span>${SPACE_NAMES[k]}</span>
      <i style="width:${Math.round(v * 100)}%"></i><b>${Math.round(v * 100)}%</b></div>`).join("") : "";
  const nums = [];
  if (sp.rt60_passive_s) nums.push(`reverberation ${sp.rt60_passive_s} s`);
  if (sp.probe && sp.probe.rt60_s) nums.push(`chirp RT60 ${sp.probe.rt60_s} s`);
  if (sp.probe && sp.probe.drr_db != null) nums.push(`DRR ${sp.probe.drr_db} dB`);
  if (sp.room_size_m) nums.push(`room ~${sp.room_size_m[0]}–${sp.room_size_m[1]} m`);
  const heard = new Set((a.events || []).map((e) => e.class));
  const chips = ["rail", "traffic", "bells", "machinery", "nature"].map((k) => {
    const e = (a.events || []).find((x) => x.class === k);
    return `<span class="chip ${heard.has(k) ? "on" : ""}">${k}${e ? " " + e.score : ""}</span>`;
  }).join("");
  const alerts = (a.alerts || []).map((x) => `<div class="meta" style="color:var(--danger)">⚠ ${esc(x.class.replace(/_/g, " "))} ${x.score}</div>`).join("");
  $("space").innerHTML = `${bars || `<div class="muted" style="font-size:13px">No spatial clue in this clip.</div>`}
    ${nums.length ? `<div class="meta">${esc(nums.join(" · "))}</div>` : ""}
    ${(sp.clues || []).length ? `<div class="meta">clues: ${esc(sp.clues.join("; "))}</div>` : ""}
    <div class="chips">${chips}</div>${alerts}
    <div class="meta">${esc(a.quality || "")} clip${(a.notes || []).length ? " · " + esc(a.notes.join("; ")) : ""}</div>`;
}

// ------------------------------------------------------------------ step 2
function tagOf(n) {
  if (/assumed|typical|unknown/.test(n)) return "assumed";
  if (/chirp|reverberation/.test(n)) return "measured";
  return "inferred";
}
function renderGuessNotes() {
  const e = scene && scene.estimate;
  if (!e) { $("guessNotes").innerHTML = ""; return; }
  const items = [];
  items.push(`<li><span class="tag">space</span><b>${esc(e.setting.label)}</b></li>`);
  for (const l of e.landmarks) items.push(`<li><span class="tag">${l.heard ? "heard" : "said"}</span><b>${esc(l.label)}</b> ${esc(l.text)}</li>`);
  if (e.sun) items.push(`<li><span class="tag">said</span><b>sun</b> ${Math.round(e.sun.beta / 30) || 12} o'clock → gives the heading</li>`);
  for (const s of e.sounds) items.push(`<li><span class="tag">${s.source === "voice" ? "said" : "audio"}</span><b>${esc(s.label)}</b> ${s.heard ? "heard" : "not heard"}</li>`);
  for (const n of e.notes) items.push(`<li><span class="tag">${tagOf(n)}</span>${esc(n)}</li>`);
  $("guessNotes").innerHTML = items.join("");
}

// ------------------------------------------------------------------ step 3
const mini = L.map("mini", { zoomControl: false, attributionControl: false }).setView([48.8435, 2.4355], 15);
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, className: "dark-tiles" }).addTo(mini);
const miniLayer = L.layerGroup().addTo(mini);
let miniKey = null;

function renderCands(rep) {
  const cs = (scene && scene.candidates) || [];
  if (!cs.length) { $("cands").innerHTML = `<div class="empty" style="padding:8px 0">No candidate area yet.</div>`; miniLayer.clearLayers(); return; }
  if (pick >= cs.length) pick = 0;
  $("cands").innerHTML = cs.map((c, i) => `<div class="cand ${i === pick ? "on" : ""}" data-i="${i}">
      <b>Area ${c.label}</b><div class="bar"><i style="width:${Math.round(c.mass * 100)}%"></i></div>
      <small>${Math.round(c.mass * 100)}% · fit ${c.fit != null ? Math.round(c.fit * 100) + "%" : "–"}</small></div>`).join("");
  document.querySelectorAll(".cand").forEach((el) => (el.onclick = () => { pick = Number(el.dataset.i); renderCands(rep); paintScenes(); }));

  miniLayer.clearLayers();
  cs.forEach((c, i) => {
    const on = i === pick;
    L.circle([c.lat, c.lon], { radius: c.radius_m, color: on ? "#e8c547" : "#8b9a94", weight: on ? 2 : 1,
                               fillOpacity: on ? 0.18 : 0.06 }).addTo(miniLayer);
    L.marker([c.lat, c.lon], { icon: L.divIcon({ className: "", html: `<div class="blob-label" style="${on ? "" : "background:#8b9a94"}">${c.label}</div>`, iconSize: [20, 20], iconAnchor: [10, 10] }) }).addTo(miniLayer);
  });
  if (rep.truth) L.circleMarker([rep.truth.lat, rep.truth.lon], { radius: 5, color: "#33e1ff", fillOpacity: 1 }).addTo(miniLayer)
    .bindTooltip("true position (rehearsal)");
  const key = scene.report_id + cs.map((c) => c.label + c.lat.toFixed(4)).join();
  if (key !== miniKey) {
    miniKey = key;
    const pts = cs.map((c) => [c.lat, c.lon]);
    if (rep.truth) pts.push([rep.truth.lat, rep.truth.lon]);
    mini.fitBounds(L.latLngBounds(pts).pad(0.4), { maxZoom: 16 });
  }
  const c = cs[pick];
  $("checks").innerHTML = c.checks.map((k) => {
    const cls = k.score >= 0.6 ? "ok" : k.score >= 0.3 ? "mid" : "bad";
    return `<li class="${cls}"><i>${k.score >= 0.6 ? "✓" : k.score >= 0.3 ? "~" : "✗"}</i><b>${esc(k.label)}</b> ${esc(k.text)}</li>`;
  }).join("");
}

function paintScenes() {
  const e = scene && scene.estimate;
  if (e) Scene3D.draw($("guess"), e, view, "Guessed from the report");
  else emptyMsg($("guess"), "Nothing described yet.");
  const c = scene && scene.candidates[pick];
  if (c) Scene3D.draw($("real"), { ...c.scene, heading: c.heading }, view, `Real surroundings · area ${c.label}`);
  else emptyMsg($("real"), "No candidate area yet.");
}

for (const id of ["guess", "real"]) {
  const cv = $(id);
  let x0 = null, y0 = null;
  cv.onpointerdown = (e) => { x0 = e.clientX; y0 = e.clientY; view.auto = false; cv.setPointerCapture(e.pointerId); };
  cv.onpointermove = (e) => {
    if (x0 == null) return;
    view.yaw += (e.clientX - x0) * 0.01;
    view.elev = Math.min(1.45, Math.max(0.2, view.elev + (e.clientY - y0) * 0.005));
    x0 = e.clientX; y0 = e.clientY; paintScenes();
  };
  cv.onpointerup = () => { x0 = null; };
  cv.ondblclick = () => { view.yaw = 0.45; view.elev = 0.6; view.auto = true; };
}
let lastPaint = 0;
(function tick(t) {
  if (view.auto && scene && t - lastPaint > 40) { view.yaw = 0.45 + Math.sin(t / 6000) * 0.4; paintScenes(); lastPaint = t; }
  requestAnimationFrame(tick);
})(0);

// ------------------------------------------------------------------ report + data
function current() { return state && state.reports.find((r) => r.id === selId); }

function render() {
  if (!state) return;
  const reps = state.reports.slice().sort((a, b) => b.created_ms - a.created_ms);
  if ($("follow").checked && reps.length) {
    const newest = state.reports.reduce((a, r) => (!a || r.updated_ms > a.updated_ms ? r : a), null);
    selId = newest.id;
  }
  if (selId && !reps.find((r) => r.id === selId)) selId = reps.length ? reps[0].id : null;
  $("rep").innerHTML = reps.length ? reps.map((r) => `<option value="${r.id}" ${r.id === selId ? "selected" : ""}>${esc(r.callsign || r.id)}${r.truth ? " (sim)" : ""}</option>`).join("")
    : `<option value="">no report yet</option>`;
  const rep = current();
  $("listenBtn").disabled = !(rep && rep.truth);
  $("answerBtn").disabled = !(rep && rep.truth && rep.question);
  if (!rep) { renderEmpty(); return; }

  const last = rep.transcripts[rep.transcripts.length - 1];
  $("said").innerHTML = `<span><b class="k">said</b>${esc(last ? last.text : "")}</span>
    <span><b class="k">read-back</b>${esc(rep.readback)}</span>`;
  renderSpace(rep);
  const key = rep.id + ":" + rep.updated_ms;
  if (key !== loadedKey) load(rep, key);
}

async function load(rep, key) {
  loadedKey = key;
  const [v, s, b, resp] = await Promise.all([
    fetch(`/api/report/${rep.id}/viz`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(`/api/report/${rep.id}/scene`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(`/api/report/${rep.id}/body`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
    fetch(`/api/report/${rep.id}/response`).then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  if (loadedKey !== key) return;          // a newer update arrived meanwhile
  // Step 4 (body3d.js is a module: it may load after us).
  if (window.Body3D) window.Body3D.show(b); else window.__pendingTwin = b;
  Impact.show(resp);                      // steps 5 and 6
  if (!scene || !s || scene.report_id !== s.report_id) pick = 0;
  viz = v && v.spec ? v : null;
  scene = s;
  drawSpec(); drawLanes(); drawEcho();
  renderGuessNotes(); renderCands(rep); paintScenes();
}

function renderEmpty() {
  viz = null; scene = null; loadedKey = null;
  Impact.show(null);
  $("said").innerHTML = `<span class="muted">Waiting for a report. Speak on <b>/field</b> or press <b>Simulate report</b>.</span>`;
  $("space").innerHTML = ""; $("guessNotes").innerHTML = ""; $("checks").innerHTML = "";
  drawSpec(); drawLanes(); drawEcho(); renderCands({}); paintScenes();
}

window.addEventListener("resize", () => { drawSpec(); drawLanes(); drawEcho(); paintScenes(); mini.invalidateSize(); });

$("rep").onchange = (e) => { selId = e.target.value; $("follow").checked = false; render(); };
$("simBtn").onclick = async (e) => {
  const b = e.target; b.disabled = true; b.textContent = "simulating…";
  const [lat, lon] = SPOTS[Math.floor(Math.random() * SPOTS.length)];
  try {
    const r = await fetch("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: lat + (Math.random() - 0.5) * 0.0008, lon: lon + (Math.random() - 0.5) * 0.0012 }) });
    const d = await r.json();
    $("follow").checked = true;
    // Then a Listen clip at the same spot, so step 1 has sound to show.
    if (d.report_id) await fetch(`/api/report/${d.report_id}/simulate_listen`, { method: "POST" });
  } finally { b.disabled = false; b.textContent = "Simulate report"; }
};
$("listenBtn").onclick = async () => { const r = current(); if (r) await fetch(`/api/report/${r.id}/simulate_listen`, { method: "POST" }); };
$("answerBtn").onclick = async () => { const r = current(); if (r) await fetch(`/api/report/${r.id}/auto_answer`, { method: "POST" }); };

function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { $("status").textContent = "live"; $("status").className = "sub live"; };
  ws.onmessage = (e) => { state = JSON.parse(e.data); render(); };
  ws.onclose = () => { $("status").textContent = "reconnecting…"; $("status").className = "sub"; setTimeout(connect, 1500); };
}
renderEmpty();
connect();
