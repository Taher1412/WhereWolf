// No network: the phone measures everything itself and talks over the radio (see radio.py).
//   Measure 4 s  -> Near-small on the phone (onnxruntime-web, offline): threats, sounds, kind of
//                   space; the end chirp -> wall distances; noise level
//   Send by radio -> a ~30-byte packet as tones (modem.js) into the radio's microphone
//   Receive route -> tones from the coordinator -> walking legs -> guidance on the phone:
//                   compass arrow, step counter, spoken turns, landmark cues (no network)
//   Hand-over QR  -> everything this phone knows, for the medic who arrives
const Phone = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const store = { get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } },
                  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } } };
  let session = null, labels = null, cues = [], last = {}, seq = 0, pendingGuide = null;

  // ------------------------------------------------------------ the model, offline
  async function model() {
    if (session) return session;
    ort.env.wasm.wasmPaths = "/static/vendor/ort/";
    ort.env.wasm.numThreads = 1;                       // no cross-origin isolation needed
    session = await ort.InferenceSession.create("/models/near-small/near_small.onnx", { executionProviders: ["wasm"] });
    labels = await (await fetch("/models/near-small/labels.json")).json();
    return session;
  }
  function resample(x, sr, to = 16000) {
    if (sr === to) return x;
    const n = Math.floor((x.length * to) / sr), y = new Float32Array(n), r = sr / to;
    for (let i = 0; i < n; i++) {                       // average over the source window (anti-alias)
      const a = Math.floor(i * r), b = Math.max(a + 1, Math.floor((i + 1) * r));
      let s = 0;
      for (let j = a; j < b && j < x.length; j++) s += x[j];
      y[i] = s / (b - a);
    }
    return y;
  }
  async function classify(x16) {
    const s = await model();
    const n = Math.min(x16.length, 16000 * 10);
    const out = await s.run({ wave: new ort.Tensor("float32", x16.slice(0, Math.max(n, 16000)), [1, Math.max(n, 16000)]) });
    const p = out.audioset.data, drone = out.heads.data[0], gunfire = out.heads.data[1], idx = {};
    labels.labels.forEach((l, i) => { idx[l] = i; });
    const grp = (names) => Math.max(0, ...names.filter((l) => l in idx).map((l) => p[idx[l]]));
    const threats = {};
    // thresholds chosen on validation clips (backend/config.py SMALL_GUN_MIN / SMALL_DRONE_MIN)
    const gs = grp(labels.groups.small_arms), boom = grp(labels.groups.explosion);
    if (gs >= 0.3 || gunfire >= 0.7) threats.small_arms = Math.max(gs, gunfire);
    if (boom >= 0.3) threats.explosion = boom;
    if (drone >= 0.7) threats.drone = drone;
    const sounds = {};
    for (const [k, names] of Object.entries(labels.sounds)) { const v = grp(names); if (v >= 0.15) sounds[k] = v; }
    const sc = {};
    for (const [k, names] of Object.entries(labels.scenes)) sc[k] = grp(names) + 0.01;
    const tot = Object.values(sc).reduce((a, b) => a + b, 0);
    for (const k in sc) sc[k] /= tot;
    const strength = Math.min(1, Math.max(...Object.values(sc)) * 1.5 - 0.375);
    return { threats, sounds, space: sc, spaceStrength: Math.max(0, strength) };
  }

  // ------------------------------------------------------------ echoes (end chirp)
  function fft(re, im) {                                // in place, length = power of 2
    const n = re.length;
    for (let i = 1, j = 0; i < n; i++) {
      let bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]]; }
    }
    for (let len = 2; len <= n; len <<= 1) {
      const a = (-2 * Math.PI) / len, wr = Math.cos(a), wi = Math.sin(a);
      for (let i = 0; i < n; i += len) {
        let cr = 1, ci = 0;
        for (let j = 0; j < len / 2; j++) {
          const ur = re[i + j], ui = im[i + j], k = i + j + len / 2;
          const vr = re[k] * cr - im[k] * ci, vi = re[k] * ci + im[k] * cr;
          re[i + j] = ur + vr; im[i + j] = ui + vi; re[k] = ur - vr; im[k] = ui - vi;
          [cr, ci] = [cr * wr - ci * wi, cr * wi + ci * wr];
        }
      }
    }
  }
  // Matched filter with the known sweep: the direct sound is the biggest peak, each wall
  // gives a later peak; distance = delay x 343 / 2. Walls 1.8-25 m, within 20 dB of direct.
  function echoes(samples, sr, pingAt, P) {
    const a = Math.max(0, Math.floor((pingAt - 0.05) * sr)), len = Math.floor((P.dur + 0.35) * sr);
    const seg = samples.slice(a, a + len);
    let n = 1; while (n < seg.length * 2) n <<= 1;
    const sw = new Float32Array(Math.floor(P.dur * sr)), k = Math.log(P.f1 / P.f0);
    for (let i = 0; i < sw.length; i++) {               // the same exponential sweep the phone played
      const t = i / sr;
      sw[i] = Math.sin(((2 * Math.PI * P.f0 * P.dur) / k) * (Math.exp((t / P.dur) * k) - 1));
    }
    const ar = new Float64Array(n), ai = new Float64Array(n), br = new Float64Array(n), bi = new Float64Array(n);
    seg.forEach((v, i) => { ar[i] = v; });
    sw.forEach((v, i) => { br[i] = v; });
    fft(ar, ai); fft(br, bi);
    for (let i = 0; i < n; i++) {                        // A * conj(B)
      const r = ar[i] * br[i] + ai[i] * bi[i], im = ai[i] * br[i] - ar[i] * bi[i];
      ar[i] = r; ai[i] = -im;                            // conj for the inverse via forward FFT
    }
    fft(ar, ai);
    const env = new Float64Array(seg.length);
    for (let i = 0; i < seg.length; i++) env[i] = Math.hypot(ar[i], ai[i]) / n;
    let d0 = 0; for (let i = 1; i < env.length; i++) if (env[i] > env[d0]) d0 = i;
    const top = env[d0], lo = top * 0.1, out = [];
    const i0 = d0 + Math.floor((2 * 1.8 / 343) * sr), i1 = Math.min(env.length - 1, d0 + Math.floor((2 * 25 / 343) * sr));
    const gap = Math.floor(0.002 * sr);
    for (let i = i0; i <= i1; i++) {
      if (env[i] < lo) continue;
      let peak = true;
      for (let j = Math.max(i0, i - gap); j <= Math.min(i1, i + gap); j++) if (env[j] > env[i]) { peak = false; break; }
      if (peak) out.push({ m: ((i - d0) / sr) * 343 / 2, v: env[i] });
    }
    return out.sort((x, y) => y.v - x.v).slice(0, 4).map((e) => Math.round(e.m * 4) / 4).sort((x, y) => x - y);
  }

  function dbfs(x) { let s = 0; for (const v of x) s += v * v; return 10 * Math.log10(s / x.length + 1e-12); }

  // ------------------------------------------------------------ Measure 4 s (offline)
  async function measure() {
    const btn = $("oMeasure");
    btn.disabled = true;
    try {
      btn.textContent = "Loading the model…";
      await model();
      btn.textContent = "Listening… stay quiet";
      const P = (typeof PROBE !== "undefined" && PROBE.f0) ? PROBE : store.get("near_probe", { f0: 800, f1: 12000, dur: 0.5, sr: 48000 });
      const cap = await rawCapture();
      const s = cap.ctx.createBufferSource();
      s.buffer = sweepBuffer(cap.ctx, P);
      s.connect(cap.ctx.destination);
      const pingAt = 3.3;
      s.start(cap.t0 + pingAt);
      await new Promise((r) => setTimeout(r, 4300));
      const rec = cap.stop();
      btn.textContent = "Analysing on the phone…";
      const quiet = rec.samples.slice(0, Math.floor(rec.sr * 3.1));
      const res = await classify(resample(quiet, rec.sr));
      res.echoes = echoes(rec.samples, rec.sr, pingAt, P);
      const cal = store.get("near_mic_cal", null);        // dBFS -> dB(A), from a voice report
      res.dba = cal != null ? Math.round(dbfs(quiet) + cal) : null;
      last = { ...last, ...res, ms: Date.now() };
      showMeasure();
    } catch (e) {
      $("oResult").textContent = "Measure failed: " + e.message;
    } finally { btn.disabled = false; btn.textContent = "Measure 4 s"; }
  }
  function showMeasure() {
    const r = last, chips = [];
    for (const [k, v] of Object.entries(r.threats || {})) chips.push(`<span class="chip warn">${esc(k.replace("_", " "))} ${v.toFixed(2)}</span>`);
    const best = r.space ? Object.entries(r.space).sort((a, b) => b[1] - a[1])[0] : null;
    if (best) chips.push(`<span class="chip">${best[0].replace("_", " ")} ${Math.round(best[1] * 100)}%</span>`);
    for (const [k, v] of Object.entries(r.sounds || {})) chips.push(`<span class="chip">${k} ${v.toFixed(2)}</span>`);
    if (r.echoes && r.echoes.length) chips.push(`<span class="chip">walls ${r.echoes.join(", ")} m</span>`);
    if (r.dba != null) chips.push(`<span class="chip">${r.dba} dB(A)</span>`);
    $("oResult").innerHTML = chips.join(" ") || "nothing heard";
  }

  // ------------------------------------------------------------ Send by radio
  function report() {
    const c = typeof compassNow === "function" ? compassNow() : null;
    const r = { callsign: $("oCall").value.trim().toUpperCase(), compass: c ? c.deg : null,
                aims: typeof aimsNow === "function" ? aimsNow() : null,
                steps: typeof steps !== "undefined" && steps.on ? steps.n : null,
                guide: pendingGuide };
    if (last.ms && Date.now() - last.ms < 10 * 60e3)
      Object.assign(r, { space: last.space, spaceStrength: last.spaceStrength, dba: last.dba, echoes: last.echoes,
                         sounds: last.sounds, threats: last.threats });
    return r;
  }
  async function send() {
    store.set("near_callsign", $("oCall").value.trim());
    const pk = Packet.encodeReport(report(), seq++);
    $("oSend").disabled = true;
    $("oSend").textContent = `Sending ${pk.length} bytes…`;
    const s = await Modem.play(pk);
    $("oSend").disabled = false;
    $("oSend").textContent = "Send by radio";
    $("oInfo").textContent = `Sent ${pk.length} bytes in ${s.toFixed(1)} s. Release PTT.`;
    pendingGuide = null;
  }

  // ------------------------------------------------------------ Receive route
  async function receive() {
    const btn = $("oRecv");
    if (btn.dataset.on) { btn.dataset.stop = "1"; return; }
    btn.dataset.on = "1";
    btn.textContent = "Listening for tones… (tap to stop)";
    const cap = await rawCapture();
    const t0 = Date.now();
    let got = null;
    while (!got && !btn.dataset.stop && Date.now() - t0 < 30000) {
      await new Promise((r) => setTimeout(r, 2500));
      const snap = cap.peek ? cap.peek() : null;
      if (snap) { const p = Modem.decode(resample(snap.samples, snap.sr, 16000), 16000).map(Packet.decodeRoute).filter(Boolean); got = p[0] || null; }
    }
    const rec = cap.stop();
    if (!got) { const p = Modem.decode(resample(rec.samples, rec.sr, 16000), 16000).map(Packet.decodeRoute).filter(Boolean); got = p[0] || null; }
    delete btn.dataset.on; delete btn.dataset.stop;
    btn.textContent = "Receive route";
    if (!got) { $("oInfo").textContent = "No route heard. Hold the phone to the radio's speaker and try again."; return; }
    startGuide(got);
  }

  // ------------------------------------------------------------ offline guidance
  let G = null, arrowTimer = null, heading = null;
  function startGuide(route) {
    G = { ...route, leg: 0, stepsAt: typeof steps !== "undefined" ? steps.n : 0 };
    store.set("near_route", G);
    $("oGuide").hidden = false;
    if (typeof startSteps === "function") startSteps(true);
    window.addEventListener("ondeviceorientationabsolute" in window ? "deviceorientationabsolute" : "deviceorientation",
      (e) => { const h = headingOf(e); if (h) heading = h.deg; });
    clearInterval(arrowTimer);
    arrowTimer = setInterval(drawGuide, 300);
    sayLeg();
  }
  function legText(i) {
    const lg = G.legs[i];
    if (!lg) return "You should see the CCP now.";
    const cue = lg.cue != null && cues[lg.cue] ? ` You should see ${cues[lg.cue].name}${lg.side ? " on your " + lg.side : ""}.` : "";
    const brg = String(Math.round((lg.bearing - 2 + 360) % 360)).padStart(3, "0");     // magnetic (2 deg East)
    return `Leg ${i + 1} of ${G.legs.length}: bearing ${brg}, about ${Math.max(10, Math.round(lg.length_m / 10) * 10)} metres.${cue}`;
  }
  function sayLeg() { const t = legText(G.leg); $("oLeg").textContent = t; if (typeof speak === "function") speak(t, "en"); }
  function drawGuide() {
    if (!G) return;
    const lg = G.legs[G.leg];
    const walked = typeof steps !== "undefined" ? (steps.n - G.stepsAt) * 0.7 : 0;
    const left = lg ? Math.max(0, lg.length_m - walked) : 0;
    $("oLeft").textContent = lg ? `${Math.round(left)} m to the next turn` : "arrived?";
    const rot = heading == null || !lg ? 0 : ((lg.bearing - 2 - heading + 540) % 360) - 180;
    $("oArrow").style.transform = `rotate(${rot}deg)`;
    $("oArrow").style.opacity = heading == null ? 0.3 : 1;
    if (lg && left <= 0 && !G.warned) { G.warned = true; if (typeof speak === "function") speak("You should be at the turn. Tap reached.", "en"); }
  }
  function reached() {
    if (!G) return;
    pendingGuide = { event: "reached", leg: G.leg };
    G.leg += 1; G.warned = false;
    G.stepsAt = typeof steps !== "undefined" ? steps.n : 0;
    store.set("near_route", G);
    if (G.leg >= G.legs.length) { pendingGuide = { event: "arrived", leg: G.leg }; $("oLeg").textContent = "You should be at the CCP."; if (typeof speak === "function") speak("You should be at the CCP.", "en"); return; }
    sayLeg();
  }

  // ------------------------------------------------------------ hand-over QR
  function qr() {
    const r = report();
    const lines = [`NEAR ${r.callsign || "?"}`, new Date().toISOString().slice(0, 16) + "Z"];
    const rb = $("readback") ? $("readback").textContent : "";
    if (rb && !rb.startsWith("Hold the button")) lines.push(rb.slice(0, 400));
    if (last.threats && Object.keys(last.threats).length) lines.push("threats: " + Object.keys(last.threats).join(", "));
    if (r.compass != null) lines.push(`facing ${Math.round(r.compass)} deg`);
    const q = qrcode(0, "M");
    q.addData(lines.join("\n"));
    q.make();
    $("oQR").innerHTML = q.createSvgTag({ cellSize: 4, margin: 2, scalable: true });
    $("oQR").hidden = false;
  }

  function init() {
    $("oCall").value = store.get("near_callsign", "");
    $("oMeasure").onclick = measure;
    $("oSend").onclick = send;
    $("oRecv").onclick = receive;
    $("oReached").onclick = reached;
    $("oQRbtn").onclick = qr;
    fetch("/api/cues").then((r) => r.json()).then((c) => { cues = c; store.set("near_cues", c); })
      .catch(() => { cues = store.get("near_cues", []); });
    fetch("/api/probe").then((r) => r.json()).then((p) => store.set("near_probe", p)).catch(() => {});
    const saved = store.get("near_route", null);
    if (saved && saved.leg < saved.legs.length) { G = saved; $("oGuide").hidden = false; $("oLeg").textContent = legText(G.leg); arrowTimer = setInterval(drawGuide, 300); }
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  }
  return { init, measure, send, receive, reached, qr, startGuide };
})();
