// Pipeline page: one report shown as steps, for the demo.
//   1 Listen  2 Reconstruct  3 Match  4 Casualty  5 Impact graph  6 Bring & send
// The drawing is shared with the coordinator page (panels.js, body3d.js, impact.js);
// this file only picks the report, runs the rehearsal buttons and the mini map.

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
let state = null, selId = null;

// Rehearsal spots around the Château de Vincennes (streets, park edge, esplanade).
const SPOTS = [[48.8437, 2.4378], [48.8452, 2.4352], [48.8418, 2.4396], [48.8466, 2.4405],
               [48.8428, 2.4335], [48.8405, 2.4370], [48.8475, 2.4365]];

// ------------------------------------------------------------------ mini map (step 3)
const mini = L.map("mini", { zoomControl: false, attributionControl: false }).setView([48.8435, 2.4355], 15);
L.tileLayer("/tiles/{z}/{x}/{y}.png", { minNativeZoom: 13, maxNativeZoom: 17, maxZoom: 19,
  bounds: L.latLngBounds([48.830, 2.405], [48.865, 2.465]) }).addTo(mini);   // offline tiles   // offline tiles
const miniLayer = L.layerGroup().addTo(mini);
let miniKey = null;

Panels.onCandidates = (cs, pick, rep) => {
  miniLayer.clearLayers();
  cs.forEach((c, i) => {
    const on = i === pick;
    L.circle([c.lat, c.lon], { radius: c.radius_m, color: on ? "#e8c547" : "#8b9a94", weight: on ? 2 : 1,
                               fillOpacity: on ? 0.18 : 0.06 }).addTo(miniLayer);
    L.marker([c.lat, c.lon], { icon: L.divIcon({ className: "", html: `<div class="blob-label" style="${on ? "" : "background:#8b9a94"}">${c.label}</div>`, iconSize: [20, 20], iconAnchor: [10, 10] }) }).addTo(miniLayer);
  });
  if (rep.truth) L.circleMarker([rep.truth.lat, rep.truth.lon], { radius: 5, color: "#33e1ff", fillOpacity: 1 }).addTo(miniLayer)
    .bindTooltip("true position (rehearsal)");
  const key = cs.map((c) => c.label + c.lat.toFixed(4)).join();
  if (cs.length && key !== miniKey) {
    miniKey = key;
    const pts = cs.map((c) => [c.lat, c.lon]);
    if (rep.truth) pts.push([rep.truth.lat, rep.truth.lon]);
    mini.fitBounds(L.latLngBounds(pts).pad(0.4), { maxZoom: 16 });
  }
};

// ------------------------------------------------------------------ report
function current() { return state && state.reports.find((r) => r.id === selId); }

function render() {
  if (!state) return;
  const reps = state.reports.slice().sort((a, b) => b.created_ms - a.created_ms);
  if ($("follow").checked && reps.length) {
    selId = state.reports.reduce((a, r) => (!a || r.updated_ms > a.updated_ms ? r : a), null).id;
  }
  if (selId && !reps.find((r) => r.id === selId)) selId = reps.length ? reps[0].id : null;
  $("rep").innerHTML = reps.length ? reps.map((r) => `<option value="${r.id}" ${r.id === selId ? "selected" : ""}>${esc(r.callsign || r.id)}${r.truth ? " (sim)" : ""}</option>`).join("")
    : `<option value="">no report yet</option>`;
  const rep = current();
  $("listenBtn").disabled = !(rep && rep.truth);
  $("answerBtn").disabled = !(rep && rep.truth && rep.question);
  if (!rep) {
    $("said").innerHTML = `<span class="muted">Waiting for a report. Speak on <b>/field</b> or press <b>Simulate report</b>.</span>`;
    Panels.load(null);
    return;
  }
  const last = rep.transcripts[rep.transcripts.length - 1];
  $("said").innerHTML = `<span><b class="k">said</b>${esc(last ? last.text : "")}</span>
    <span><b class="k">read-back</b>${esc(rep.readback)}</span>`;
  Panels.load(rep);
}

window.addEventListener("resize", () => mini.invalidateSize());
$("rep").onchange = (e) => { selId = e.target.value; $("follow").checked = false; render(); };
$("simBtn").onclick = async (e) => {
  const b = e.target; b.disabled = true; b.textContent = "simulating…";
  const [lat, lon] = SPOTS[Math.floor(Math.random() * SPOTS.length)];
  try {
    const r = await fetch("/api/simulate", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ lat: lat + (Math.random() - 0.5) * 0.0008, lon: lon + (Math.random() - 0.5) * 0.0012 }) });
    const d = await r.json();
    $("follow").checked = true;
    // The simulated report already carries its own audio (voice + end chirp).
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
Panels.load(null);
connect();
