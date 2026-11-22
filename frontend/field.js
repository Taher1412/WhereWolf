// Field page: push-to-talk -> text -> /api/report -> spoken read-back.
const $ = (id) => document.getElementById(id);
let reportId = sessionStorage.getItem("near_report") || null;
let busy = false;

// ---------------------------------------------------------------- speech out
function speak(text, lang, rate = 1.0) {
  if (!$("speak").checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang === "fr" ? "fr-FR" : "en-GB";
  u.rate = rate;
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- send report
async function getGps() {
  if (!$("gps").checked || !navigator.geolocation) return null;
  return new Promise((res) => navigator.geolocation.getCurrentPosition(
    (p) => { keepFix(p); res({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }); },
    () => res(null), { timeout: 4000, maximumAge: 10000 }));
}

// ---------------------------------------------------------------- last fix before jamming
// Opt-in: remember every good fix; when GPS is gone, send the last one with its age.
const FIX_KEY = "near_lastfix";
let fixWatch = null;
function keepFix(p) {
  if (p.coords.accuracy > 100) return;   // a jammed / spoofed-looking fix is not worth keeping
  localStorage.setItem(FIX_KEY, JSON.stringify({ lat: p.coords.latitude, lon: p.coords.longitude,
                                                 acc: p.coords.accuracy, ms: Date.now() }));
}
function watchFix() {
  if (fixWatch !== null) { navigator.geolocation.clearWatch(fixWatch); fixWatch = null; }
  if ($("lastfix") && $("lastfix").checked && navigator.geolocation)
    fixWatch = navigator.geolocation.watchPosition(keepFix, () => {}, { enableHighAccuracy: true, maximumAge: 30000 });
}
function lastFix(live) {
  if (live || !$("lastfix") || !$("lastfix").checked) return null;
  const f = JSON.parse(localStorage.getItem(FIX_KEY) || "null");
  if (!f || Date.now() - f.ms > 3 * 3600e3) return null;   // older than 3 h: useless
  return { lat: f.lat, lon: f.lon, acc: f.acc, age_s: Math.round((Date.now() - f.ms) / 1000) };
}

// ---------------------------------------------------------------- compass
// "My 12 o'clock": the phone held flat, top edge where the speaker faces. Fixes the
// heading like the sun does, and works under trees. Phone compasses are ~±25 deg.
let compass = null;   // {deg, acc, ms}
function headingOf(e) {
  if (typeof e.webkitCompassHeading === "number" && e.webkitCompassHeading >= 0)      // iOS
    return { deg: e.webkitCompassHeading, acc: e.webkitCompassAccuracy >= 0 ? e.webkitCompassAccuracy : null };
  if (e.absolute && typeof e.alpha === "number") return { deg: (360 - e.alpha) % 360, acc: null };   // Android
  return null;
}
async function readCompass(ms = 1200) {
  if (typeof DeviceOrientationEvent === "undefined") return null;
  if (typeof DeviceOrientationEvent.requestPermission === "function") {   // iOS: needs the tap
    try { if ((await DeviceOrientationEvent.requestPermission()) !== "granted") return null; } catch (e) { return null; }
  }
  const evt = "ondeviceorientationabsolute" in window ? "deviceorientationabsolute" : "deviceorientation";
  return new Promise((res) => {
    let S = 0, C = 0, n = 0, accs = [];
    const on = (e) => {
      const h = headingOf(e);
      if (!h) return;
      S += Math.sin(h.deg * Math.PI / 180); C += Math.cos(h.deg * Math.PI / 180); n++;
      if (h.acc != null) accs.push(h.acc);
    };
    window.addEventListener(evt, on);
    setTimeout(() => {
      window.removeEventListener(evt, on);
      if (!n) return res(null);
      const deg = (Math.atan2(S, C) * 180 / Math.PI + 360) % 360;
      const R = Math.hypot(S, C) / n;                                   // 1 = steady
      const spread = Math.sqrt(-2 * Math.log(Math.max(R, 1e-6))) * 180 / Math.PI;
      const acc = Math.max(spread, accs.length ? accs.reduce((a, b) => a + b) / accs.length : 0);
      res({ deg: Math.round(deg), acc: Math.round(acc), ms: Date.now() });
    }, ms);
  });
}
const CARD = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
async function setCompass() {
  $("compass").textContent = "reading… keep still";
  const c = await readCompass();
  if (!c) { $("compass").textContent = "no compass on this phone"; return; }
  compass = c;
  $("compass").textContent = `12 o'clock = ${c.deg}° ${CARD[Math.round(c.deg / 45) % 8]}` + (c.acc > 25 ? ` (unsteady ±${c.acc}°)` : "");
}
function compassNow() {   // sent with every report for 5 minutes after it was set
  return compass && Date.now() - compass.ms < 5 * 60e3 ? { deg: compass.deg, acc: compass.acc } : null;
}

// ---------------------------------------------------------------- aim & tap
// Top edge of the phone on the top of a landmark: beta = elevation angle (tilt), -alpha =
// azimuth of the top edge (W3C: R = Rz(alpha) Rx(beta) Ry(gamma) leaves the device y axis
// at azimuth -alpha, elevation beta). The gyroscope's relative alpha is steady over a few
// seconds, so the turn between two taps is good to ~2 deg without any compass.
let aims = [], orient = [], orientOn = false;
function onOrient(e) {
  if (typeof e.alpha !== "number" || typeof e.beta !== "number") return;
  orient.push({ a: e.alpha, b: e.beta, t: performance.now() });
  if (orient.length > 30) orient.shift();
}
async function startOrient() {
  if (orientOn) return true;
  if (typeof DeviceOrientationEvent === "undefined") return false;
  if (typeof DeviceOrientationEvent.requestPermission === "function") {
    try { if ((await DeviceOrientationEvent.requestPermission()) !== "granted") return false; } catch (e) { return false; }
  }
  window.addEventListener("deviceorientation", onOrient);
  orientOn = true;
  await new Promise((r) => setTimeout(r, 300));
  return true;
}
function wrap180(a) { return ((a + 180) % 360 + 360) % 360 - 180; }
function showAims() {
  if (!aims.length) { $("aims").textContent = "no aim"; return; }
  $("aims").textContent = aims.map((m, i) => i === 0 ? `1: ${m.el.toFixed(0)}° up`
    : `${i + 1}: ${Math.abs(m.az).toFixed(0)}° ${m.az >= 0 ? "right" : "left"} of 1, ${m.el.toFixed(0)}° up`).join(" · ");
}
async function aimTap() {
  if (!(await startOrient())) { $("aims").textContent = "no motion sensor on this phone"; return; }
  const now = performance.now(), recent = orient.filter((o) => now - o.t < 400);
  if (!recent.length) { $("aims").textContent = "hold still and tap again"; return; }
  let S = 0, C = 0, B = 0;
  for (const o of recent) { S += Math.sin(-o.a * Math.PI / 180); C += Math.cos(-o.a * Math.PI / 180); B += o.b; }
  const azAbs = Math.atan2(S, C) * 180 / Math.PI, el = B / recent.length;
  if (el < -10 || el > 85) { $("aims").textContent = "tilt the top edge up at the landmark's top, screen facing you"; return; }
  const first = aims.length ? aims[0]._abs : azAbs;
  aims.push({ az: aims.length ? wrap180(azAbs - first) : 0, el, _abs: azAbs });
  if (navigator.vibrate) navigator.vibrate(30);
  showAims();
}
function aimsNow() { return aims.length ? aims.map((m) => ({ az: Math.round(m.az * 10) / 10, el: Math.round(m.el * 10) / 10 })) : null; }

// ---------------------------------------------------------------- pulse (chest audio)
// 10 s with the microphone pressed on the chest: the heart sounds give the heart rate
// (backend/heart.py). The voice alone cannot.
let pulsing = false;
async function pulse() {
  if (pulsing || recording || busy) return;
  if (!navigator.mediaDevices || !window.isSecureContext) { $("aims").textContent = "microphone needs HTTPS"; return; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  pulsing = true;
  const btn = $("pulsebtn"), total = 10;
  let cap;
  try { cap = await rawCapture(); } catch (e) { pulsing = false; btn.textContent = "🫀 no mic"; return; }
  const t0 = Date.now();
  const tick = setInterval(() => { btn.textContent = `🫀 hold still… ${Math.max(0, total - (Date.now() - t0) / 1000).toFixed(0)} s`; }, 200);
  await new Promise((r) => setTimeout(r, total * 1000));
  clearInterval(tick);
  const rec = cap.stop();
  btn.textContent = "🫀 measuring…";
  try {
    const fd = new FormData();
    fd.append("audio", wavBlob(rec.samples, rec.sr), "pulse.wav");
    if (reportId) fd.append("report_id", reportId);
    const r = await fetch("/api/pulse", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    const p = d.pulse || {};
    btn.textContent = p.bpm ? `🫀 ${p.ok ? "" : "~"}${p.bpm} bpm` : "🫀 Pulse";
    if (!p.ok) $("aims").textContent = p.reason || "unclear: press firmly and repeat";
    reportId = d.report_id; sessionStorage.setItem("pothenot_report", reportId);
  } catch (e) { btn.textContent = "🫀 failed: " + e.message; }
  pulsing = false;
}

async function send(text, source) {
  text = (text || "").trim();
  if (!text || busy) return;
  busy = true;
  $("ptt").classList.add("busy");
  addLog("you", text);
  try {
    const gps = await getGps();
    // The voice of this report: wait for the end chirp (the read-back would be recorded on
    // top), measure how the speaker sounds (fast, ~0.2 s) so the question asked now fits
    // their stress, then send the clip for the full analysis (background level, echoes).
    let v = null, voice = null;
    if (pendingVoice) {
      const p = pendingVoice; pendingVoice = null;
      v = await p;
      if (v.rec.samples.length > v.rec.sr * 1.5) voice = await quickVoice(v.rec, v.pingAt);
      else v = null;
    }
    const r = await fetch("/api/report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_id: reportId, text, source, gps,
        compass: compassNow(), last_fix: lastFix(gps), aims: aimsNow(), voice,
        lang: $("lang").value.slice(0, 2) }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    if (aims.length) { aims = []; showAims(); }      // used by this report
    if (v) uploadAudio(v.rec, "voice", v.pingAt, false);
    show(d);
  } catch (e) {
    $("readback").textContent = "Error: " + e.message + ". Try again.";
  } finally {
    busy = false;
    $("ptt").classList.remove("busy");
  }
}

async function quickVoice(rec, pingAt) {
  try {
    const fd = new FormData();
    fd.append("audio", wavBlob(rec.samples, rec.sr), "voice.wav");
    if (pingAt != null) fd.append("ping_at", String(pingAt));
    const ctl = new AbortController(), timer = setTimeout(() => ctl.abort(), 3000);
    const r = await fetch("/api/voice_quick", { method: "POST", body: fd, signal: ctl.signal });
    clearTimeout(timer);
    return r.ok ? (await r.json()).voice : null;
  } catch (e) { return null; }    // no stress measure this time: the report still goes
}

function showAcoustic(a) {
  if (!a) return;
  const sp = a.space || {};
  const ok = sp.strength >= 0.15 && sp.p_best >= 0.5;
  let txt = ok ? sp.label : "space unclear";
  const pr = sp.probe || {};
  if (pr.ok && pr.wall_reliable && pr.nearest_wall_m) txt += ` · wall ~${pr.nearest_wall_m.toFixed(1)} m`;
  if (sp.room_size_m) txt += ` · ~${sp.room_size_m[0]}–${sp.room_size_m[1]} m across`;
  $("space").textContent = txt;
  $("space").className = "chip " + (ok ? "ok" : "");
  const ev = (a.events || []).filter((e) => e.score >= 0.2).map((e) => e.class);
  if (a.kind !== "voice") $("heard").textContent = ev.length ? "heard: " + ev.join(", ") : "no clear sound source";
  if (a.notes && a.notes.length) $("listenhint").textContent = a.notes.join(" · ");
  if (pr.ok === false && pr.why) $("listenhint").textContent = "chirp: " + pr.why;
}

function show(d) {
  showAcoustic(d.acoustic);
  reportId = d.report_id;
  sessionStorage.setItem("near_report", reportId);
  $("rid").textContent = "report " + reportId;
  $("readback").textContent = d.readback;
  if (d.question) {
    $("qcard").style.display = "block"; $("question").textContent = d.question;
    $("qgoal").textContent = d.goal || "";
  } else { $("qcard").style.display = "none"; }
  const cd = $("cond"), c = d.condition;
  if (cd) {
    cd.textContent = c ? `casualty: ${c.state}${c.worse_in ? ` · worse in ${Math.round(c.worse_in.min)}–${Math.round(c.worse_in.max)} min` : ""}` : "casualty —";
    cd.className = "chip " + (c && c.score < 50 ? "warn" : "");
  }
  const st = $("stress");
  if (st) { st.textContent = d.stress && d.stress !== "unknown" ? `voice: ${d.stress} stress` : "voice —";
            st.className = "chip " + (d.stress === "high" ? "warn" : ""); }
  const r = $("radius");
  r.textContent = d.radius_m ? `± ${d.radius_m} m` : "position —";
  r.className = "chip " + (d.state === "confirmed" ? "ok" : d.radius_m ? "warn" : "");
  const s = d.summary || {};
  $("prio").textContent = s.count ? `P${s.rank} · ${s.count} cas.` : "priority —";
  $("prio").className = "chip " + (s.rank === 1 ? "warn" : "");
  if (d.packet) $("bytes").textContent = `${d.packet.bytes} B packet`;
  addLog("near", d.readback);
  speak(d.readback, d.lang, d.stress === "high" ? 0.88 : 1.0);   // calmer, slower when stressed
  showGuide(d, false);
}

// ---------------------------------------------------------------- guidance to the CCP
// Once located, a casualty who can walk gets a route (backend/guide.py). The phone polls
// for the next instruction, speaks it, and counts steps so the map pin follows the walker.
let guideSay = 0, guidePoll = null, lastLang = "en";
function showGuide(d, speakNew = true) {
  const g = d.guide;
  lastLang = d.lang || lastLang;
  if (!g || g.state === "stopped") { $("gcard").style.display = "none"; stopGuidePoll(); return; }
  $("gcard").style.display = "block";
  $("ginstr").textContent = g.instruction || "";
  $("gprog").textContent = g.state === "active" ? `· leg ${g.leg} / ${g.legs}` : g.state === "arrived" ? "· arrived" : "· " + g.state;
  $("gleft").textContent = g.state === "arrived" ? "at the CCP" : `${g.left_m} m left · ~${Math.max(1, Math.round(g.eta_s / 60))} min`;
  $("gleft").className = "chip " + (g.state === "arrived" ? "ok" : "");
  const active = g.state === "active" || g.state === "lost";
  ["greached", "grepeat", "glost", "garrived"].forEach((id) => { $(id).disabled = !active; });
  if (speakNew && g.say_v > guideSay && g.instruction) { addLog("near", g.instruction); speak(g.instruction, d.lang); }
  guideSay = Math.max(guideSay, g.say_v);
  if (active) { startGuidePoll(); startSteps(); } else stopGuidePoll();
}
function startGuidePoll() {
  if (guidePoll) return;
  guidePoll = setInterval(async () => {
    if (!reportId) return;
    try {
      if (steps.n !== steps.sent && steps.on) {
        steps.sent = steps.n;
        await guideAction("steps", { steps: steps.n }, false);
      }
      const r = await fetch(`/api/report/${reportId}/guide`);
      if (r.ok) showGuide(await r.json());
    } catch (e) { /* offline for a moment: keep the last instruction */ }
  }, 3000);
}
function stopGuidePoll() { if (guidePoll) { clearInterval(guidePoll); guidePoll = null; } }
async function guideAction(action, extra = {}, render = true) {
  if (!reportId) return;
  const r = await fetch(`/api/report/${reportId}/guide`, { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...extra }) });
  if (!r.ok || !render) return;
  const d = await r.json();
  $("readback").textContent = d.readback;
  addLog("near", d.readback);
  speak(d.readback, d.lang);
  if (d.guide) guideSay = Math.max(guideSay, d.guide.say_v);
  showGuide(d, false);
}
$("greached").addEventListener("click", () => { startSteps(true); guideAction("reached"); });
$("grepeat").addEventListener("click", () => guideAction("repeat"));
$("glost").addEventListener("click", () => guideAction("lost"));
$("garrived").addEventListener("click", () => guideAction("arrived"));

// Step counter from the accelerometer: a step is a peak of |acceleration| above the
// running mean, at least 0.3 s after the previous one. Good to ~10 % when walking.
const steps = { on: false, n: 0, sent: 0, mean: 9.81, last: 0, up: false };
function onMotion(e) {
  const a = e.accelerationIncludingGravity;
  if (!a || a.x == null) return;
  const m = Math.hypot(a.x, a.y, a.z);
  steps.mean = 0.98 * steps.mean + 0.02 * m;
  const t = performance.now();
  if (!steps.up && m > steps.mean + 1.3 && t - steps.last > 300) { steps.up = true; steps.last = t; steps.n++; }
  else if (steps.up && m < steps.mean) steps.up = false;
  $("gsteps").textContent = `${steps.n} steps`;
  $("gsteps").className = "chip ok";
}
async function startSteps(fromTap = false) {
  if (steps.on || typeof DeviceMotionEvent === "undefined") return;
  if (typeof DeviceMotionEvent.requestPermission === "function") {   // iOS: only from a tap
    if (!fromTap) { $("gsteps").textContent = "tap Reached to count steps"; return; }
    try { if ((await DeviceMotionEvent.requestPermission()) !== "granted") return; } catch (e) { return; }
  }
  window.addEventListener("devicemotion", onMotion);
  steps.on = true;
}

function addLog(who, text) {
  const div = document.createElement("div");
  div.innerHTML = `<b>${who}:</b> `;
  div.appendChild(document.createTextNode(text));
  $("log").prepend(div);
}

// ---------------------------------------------------------------- raw audio (acoustics)
// Lossless PCM straight from the mic, with every browser "enhancement" off:
// echo cancellation / noise suppression would delete the echoes we measure.
const RAW_CONSTRAINTS = { audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false,
                                   channelCount: 1 } };
let listening = false, pendingVoice = null, voiceCap = null;

async function rawCapture() {
  const stream = await navigator.mediaDevices.getUserMedia(RAW_CONSTRAINTS);
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  if (ctx.state === "suspended") await ctx.resume();
  const src = ctx.createMediaStreamSource(stream);
  const proc = ctx.createScriptProcessor(4096, 1, 1);
  const mute = ctx.createGain(); mute.gain.value = 0;
  const bufs = [];
  proc.onaudioprocess = (e) => bufs.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  src.connect(proc); proc.connect(mute); mute.connect(ctx.destination);
  return {
    ctx, t0: ctx.currentTime,
    stop() {
      proc.disconnect(); src.disconnect(); stream.getTracks().forEach((t) => t.stop());
      const n = bufs.reduce((a, b) => a + b.length, 0), all = new Float32Array(n);
      let o = 0; for (const b of bufs) { all.set(b, o); o += b.length; }
      const sr = ctx.sampleRate; ctx.close();
      return { samples: all, sr };
    },
  };
}

function wavBlob(samples, sr) {
  const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
  const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, sr, true);
  v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data");
  v.setUint32(40, samples.length * 2, true);
  for (let i = 0; i < samples.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 0x7fff, true);
  return new Blob([buf], { type: "audio/wav" });
}

// Same exponential sweep as backend/spatial.py make_sweep (5 ms fades).
function sweepBuffer(ctx, p) {
  const sr = ctx.sampleRate, n = Math.floor(p.dur * sr), L = p.dur / Math.log(p.f1 / p.f0);
  const b = ctx.createBuffer(1, n, sr), x = b.getChannelData(0), nf = Math.floor(0.005 * sr);
  for (let i = 0; i < n; i++) {
    const t = i / sr;
    let a = Math.sin(2 * Math.PI * p.f0 * L * (Math.exp(t / L) - 1));
    if (i < nf) a *= 0.5 - 0.5 * Math.cos(Math.PI * i / (nf - 1));
    if (i >= n - nf) a *= 0.5 - 0.5 * Math.cos(Math.PI * (n - 1 - i) / (nf - 1));
    x[i] = a * 0.9;
  }
  return b;
}

let PROBE = { f0: 800, f1: 12000, dur: 0.5, sr: 48000 };

// End chirp: right after the voice, the phone plays the echo-ranging sweep and keeps
// recording ~1 s, so every report also measures the walls around (no extra step).
// Resolves to { rec, pingAt } (pingAt = seconds into the recording, or null).
function finishVoice(cap) {
  if (!$("endchirp") || !$("endchirp").checked) return Promise.resolve({ rec: cap.stop(), pingAt: null });
  const s = cap.ctx.createBufferSource();
  s.buffer = sweepBuffer(cap.ctx, PROBE);
  s.connect(cap.ctx.destination);
  const at = cap.ctx.currentTime + 0.08;
  s.start(at);
  return new Promise((res) => setTimeout(() => res({ rec: cap.stop(), pingAt: at - cap.t0 }), (PROBE.dur + 0.95) * 1000));
}
fetch("/api/probe").then((r) => r.json()).then((p) => { PROBE = p; }).catch(() => {});

async function uploadAudio(rec, kind, pingAt, showBusy = true) {
  const fd = new FormData();
  fd.append("audio", wavBlob(rec.samples, rec.sr), kind + ".wav");
  if (reportId) fd.append("report_id", reportId);
  fd.append("kind", kind);
  if (pingAt != null) fd.append("ping_at", String(pingAt));
  try {
    const r = await fetch("/api/audio", { method: "POST", body: fd });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    if (kind === "voice") { showAcoustic(d.acoustic); return; }   // quiet: no new read-back
    show(d);
  } catch (e) {
    if (showBusy) $("listenhint").textContent = "Sound analysis failed: " + e.message;
  }
}

async function listen() {
  if (listening || recording || busy) return;
  if (!navigator.mediaDevices || !window.isSecureContext) {
    $("listenhint").textContent = "Microphone needs HTTPS (python run.py --https)."; return;
  }
  if ("speechSynthesis" in window) speechSynthesis.cancel();      // don't record our own voice
  listening = true;
  $("listen").classList.add("rec");
  const chirp = $("chirp").checked, total = chirp ? 4.5 : 4.0, pingAt = 1.0;
  let cap;
  try { cap = await rawCapture(); }
  catch (e) { listening = false; $("listen").classList.remove("rec");
              $("listenhint").textContent = "No microphone: " + e.message; return; }
  if (chirp) {
    const s = cap.ctx.createBufferSource();
    s.buffer = sweepBuffer(cap.ctx, PROBE);
    s.connect(cap.ctx.destination);
    s.start(cap.t0 + pingAt);
  }
  const t0 = Date.now();
  const tick = setInterval(() => {
    $("listen").textContent = `Listening… ${Math.max(0, total - (Date.now() - t0) / 1000).toFixed(1)} s`;
  }, 100);
  await new Promise((r) => setTimeout(r, total * 1000));
  clearInterval(tick);
  const rec = cap.stop();
  $("listen").textContent = "Analysing…";
  await uploadAudio(rec, "ambient", chirp ? pingAt : null);
  $("listen").textContent = "Listen 4 s";
  $("listen").classList.remove("rec");
  listening = false;
}
$("listen").addEventListener("click", listen);
$("compassbtn").addEventListener("click", setCompass);
$("aimbtn").addEventListener("click", aimTap);
$("pulsebtn").addEventListener("click", pulse);
$("aimclear").addEventListener("click", () => { aims = []; showAims(); });
$("lastfix").addEventListener("change", watchFix);
watchFix();

// ---------------------------------------------------------------- speech in
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, recording = false, finalText = "", mediaRec = null, chunks = [];
// Some phones won't share the mic between speech recognition and our raw capture:
// if that breaks recognition once, we stop trying on this device.
const VOICE_CAP_OFF = "near_voicecap_off";
function voiceCapAllowed() {
  try { return $("voiceac").checked && !localStorage.getItem(VOICE_CAP_OFF); } catch { return $("voiceac").checked; }
}

function startRec() {
  if (recording || busy || listening) return;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  recording = true;
  finalText = "";
  $("ptt").classList.add("rec");
  $("interim").textContent = "listening… speak now";
  voiceCap = null;
  pendingVoice = null;     // a clip from a report that never got sent
  if (SR) {
    let heard = "", errored = null, wantCap = voiceCapAllowed() && window.isSecureContext;
    rec = new SR();
    rec.lang = $("lang").value;
    rec.continuous = true;
    rec.interimResults = true;
    // Raw voice capture (room acoustics) starts only once recognition owns the mic.
    rec.onaudiostart = () => {
      if (wantCap && recording)
        rawCapture().then((c) => { if (recording) voiceCap = c; else c.stop(); }).catch(() => {});
    };
    rec.onresult = (e) => {
      let interim = "";
      finalText = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript + " ";
        else interim += e.results[i][0].transcript;
      }
      heard = (finalText + interim).trim();
      $("interim").textContent = heard || "listening… speak now";
    };
    rec.onerror = (e) => {
      errored = e.error;
      console.warn("[near] speech recognition error:", e.error, e.message || "");
      const why = { "no-speech": "no speech heard, try again closer to the mic",
                    "not-allowed": "microphone blocked: allow it in the address bar",
                    "audio-capture": "no microphone available",
                    "network": "speech service unreachable (needs internet): type the report below" }[e.error] || e.error;
      $("interim").textContent = "Mic: " + why;
      if (e.error === "audio-capture" && wantCap) {     // our raw capture may be blocking the mic
        try { localStorage.setItem(VOICE_CAP_OFF, "1"); } catch {}
        $("interim").textContent += " (voice acoustics now off on this device, try again)";
      }
    };
    rec.onend = () => {
      const text = (finalText || heard).trim();        // never the on-screen error text
      if (recording) {                                  // ended by itself (silence, error)
        recording = false;
        $("ptt").classList.remove("rec");
        if (voiceCap) { const c = voiceCap; voiceCap = null;
                        if (text) pendingVoice = finishVoice(c); else c.stop(); }
      }
      if (!errored || text) $("interim").textContent = "";
      if (text) send(text, "voice");
    };
    rec.start();
  } else if (navigator.mediaDevices && window.MediaRecorder) {
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      chunks = [];
      mediaRec = new MediaRecorder(stream);
      mediaRec.ondataavailable = (e) => chunks.push(e.data);
      mediaRec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        $("interim").textContent = "transcribing…";
        const fd = new FormData();
        fd.append("audio", new Blob(chunks, { type: mediaRec.mimeType }), "report.webm");
        fd.append("lang", $("lang").value.slice(0, 2));
        try {
          const r = await fetch("/api/transcribe", { method: "POST", body: fd });
          const d = await r.json();
          if (!r.ok) throw new Error(d.error);
          $("interim").textContent = "";
          send(d.text, "voice");
        } catch (e) { $("interim").textContent = "transcription failed: " + e.message; }
      };
      mediaRec.start();
    }).catch((e) => { recording = false; $("ptt").classList.remove("rec");
                      $("interim").textContent = "no microphone: " + e.message; });
  } else {
    recording = false;
    $("ptt").classList.remove("rec");
    $("interim").textContent = "No speech support here: type the report below.";
  }
}

function stopRec() {
  if (!recording) return;
  recording = false;
  $("ptt").classList.remove("rec");
  if (voiceCap) {                                                  // sent after the report
    const c = voiceCap; voiceCap = null;
    pendingVoice = finishVoice(c);
  }
  if (rec) { rec.stop(); rec = null; }
  if (mediaRec && mediaRec.state !== "inactive") mediaRec.stop();
}

// Hold to talk; a short tap toggles instead (easier with gloves).
let downAt = 0;
$("ptt").addEventListener("pointerdown", (e) => {
  e.preventDefault();
  if (recording) { stopRec(); downAt = 0; return; }
  downAt = Date.now();
  startRec();
});
$("ptt").addEventListener("pointerup", () => {
  if (downAt && Date.now() - downAt > 400) stopRec();   // long press = hold to talk
  else if (recording) $("interim").textContent = "listening… tap again to send";
  downAt = 0;
});
$("ptt").addEventListener("contextmenu", (e) => e.preventDefault());
// Space bar = push to talk on a laptop.
document.addEventListener("keydown", (e) => {
  if (e.code === "Space" && document.activeElement.tagName !== "INPUT" && !e.repeat) { e.preventDefault(); startRec(); }
});
document.addEventListener("keyup", (e) => {
  if (e.code === "Space" && document.activeElement.tagName !== "INPUT") { e.preventDefault(); stopRec(); }
});

$("typed").addEventListener("submit", (e) => {
  e.preventDefault();
  send($("text").value, "typed");
  $("text").value = "";
});

$("newbtn").addEventListener("click", () => {
  stopGuidePoll(); guideSay = 0; $("gcard").style.display = "none";
  reportId = null;
  sessionStorage.removeItem("near_report");
  $("rid").textContent = "no report";
  $("readback").textContent = "New casualty. Hold the button and report.";
  $("qcard").style.display = "none";
  $("log").innerHTML = "";
  ["radius", "prio", "bytes", "space", "heard"].forEach((id) => { $(id).className = "chip"; });
  $("radius").textContent = "position —"; $("prio").textContent = "priority —"; $("bytes").textContent = "packet —";
  $("space").textContent = "space —"; $("heard").textContent = "sounds —";
});

$("engine").textContent = SR ? "Speech: browser recognition" :
  (window.MediaRecorder ? "Speech: server transcription" : "Speech: not available, type instead");
if (!window.isSecureContext && location.hostname !== "localhost")
  $("engine").textContent += " · microphone needs HTTPS (python run.py --https)";
if (reportId) $("rid").textContent = "report " + reportId;

// Page reloaded in the middle of a walk: pick the guidance up again.
if (reportId) fetch(`/api/report/${reportId}/guide`).then((r) => (r.ok ? r.json() : null))
  .then((d) => { if (d && d.guide) { guideSay = d.guide.say_v; showGuide(d, false); } }).catch(() => {});
