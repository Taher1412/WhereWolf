// Field page: push-to-talk -> text -> /api/report -> spoken read-back.
const $ = (id) => document.getElementById(id);
let reportId = sessionStorage.getItem("pothenot_report") || null;
let busy = false;

// ---------------------------------------------------------------- speech out
function speak(text, lang) {
  if (!$("speak").checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang === "fr" ? "fr-FR" : "en-GB";
  u.rate = 1.0;
  speechSynthesis.speak(u);
}

// ---------------------------------------------------------------- send report
async function getGps() {
  if (!$("gps").checked || !navigator.geolocation) return null;
  return new Promise((res) => navigator.geolocation.getCurrentPosition(
    (p) => res({ lat: p.coords.latitude, lon: p.coords.longitude, acc: p.coords.accuracy }),
    () => res(null), { timeout: 4000, maximumAge: 10000 }));
}

async function send(text, source) {
  text = (text || "").trim();
  if (!text || busy) return;
  busy = true;
  $("ptt").classList.add("busy");
  addLog("you", text);
  try {
    const r = await fetch("/api/report", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ report_id: reportId, text, source,
        gps: await getGps(), lang: $("lang").value.slice(0, 2) }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || r.statusText);
    show(d);
    // The voice of this report = a free test signal for the room's reverberation.
    if (pendingVoice) { const v = pendingVoice; pendingVoice = null; uploadAudio(v, "voice", null, false); }
  } catch (e) {
    $("readback").textContent = "Error: " + e.message + ". Try again.";
  } finally {
    busy = false;
    $("ptt").classList.remove("busy");
  }
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
  sessionStorage.setItem("pothenot_report", reportId);
  $("rid").textContent = "report " + reportId;
  $("readback").textContent = d.readback;
  if (d.question) { $("qcard").style.display = "block"; $("question").textContent = d.question; }
  else { $("qcard").style.display = "none"; }
  const r = $("radius");
  r.textContent = d.radius_m ? `± ${d.radius_m} m` : "position —";
  r.className = "chip " + (d.state === "confirmed" ? "ok" : d.radius_m ? "warn" : "");
  const s = d.summary || {};
  $("prio").textContent = s.count ? `P${s.rank} · ${s.count} cas.` : "priority —";
  $("prio").className = "chip " + (s.rank === 1 ? "warn" : "");
  if (d.packet) $("bytes").textContent = `${d.packet.bytes} B packet`;
  addLog("pothenot", d.readback);
  speak(d.readback, d.lang);
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

// ---------------------------------------------------------------- speech in
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, recording = false, finalText = "", mediaRec = null, chunks = [];
// Some phones won't share the mic between speech recognition and our raw capture:
// if that breaks recognition once, we stop trying on this device.
const VOICE_CAP_OFF = "pothenot_voicecap_off";
function voiceCapAllowed() {
  try { return $("voiceac").checked && !localStorage.getItem(VOICE_CAP_OFF); } catch { return $("voiceac").checked; }
}

function startRec() {
  if (recording || busy || listening) return;
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  recording = true;
  finalText = "";
  $("ptt").classList.add("rec");
  $("interim").textContent = "listening…";
  voiceCap = null;
  if (SR && voiceCapAllowed() && window.isSecureContext)
    rawCapture().then((c) => { if (recording) voiceCap = c; else c.stop(); }).catch(() => {});
  if (SR) {
    rec = new SR();
    rec.lang = $("lang").value;
    rec.continuous = true;
    rec.interimResults = true;
    rec.onresult = (e) => {
      let interim = "";
      finalText = "";
      for (let i = 0; i < e.results.length; i++) {
        if (e.results[i].isFinal) finalText += e.results[i][0].transcript + " ";
        else interim += e.results[i][0].transcript;
      }
      $("interim").textContent = (finalText + interim).trim() || "listening…";
    };
    rec.onerror = (e) => {
      $("interim").textContent = "mic error: " + e.error;
      if (e.error === "audio-capture" && voiceCap) {     // mic can't be shared on this phone
        try { localStorage.setItem(VOICE_CAP_OFF, "1"); } catch {}
        $("interim").textContent += " (voice acoustics turned off on this phone, try again)";
      }
    };
    rec.onend = () => {
      const text = (finalText || $("interim").textContent.replace("listening…", "")).trim();
      $("interim").textContent = "";
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
  if (voiceCap) {
    const r = voiceCap.stop(); voiceCap = null;
    if (r.samples.length > r.sr * 1.5) pendingVoice = r;          // sent after the report
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
  reportId = null;
  sessionStorage.removeItem("pothenot_report");
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
