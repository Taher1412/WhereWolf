// Radio mode (backend/radio.py): the laptop listens to the tactical radio, no internet.
//   radio speaker out -> laptop audio in -> this page cuts each transmission (voice activity)
//   -> /api/radio (data tones, local Whisper, threats, callsign) -> reply
//   -> the operator approves -> offline voice (/api/tts) played on the output wired to the
//      radio's microphone (setSinkId). Route tones for a walker's phone the same way.
// "Use a recording" sends a file instead (rehearsal without a radio).
const Radio = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let ctx = null, src = null, proc = null, stream = null, on = false, sending = false;
  let floor = 0.003, buf = [], speaking = false, quietMs = 0, startedAt = 0;
  const HANG_MS = 900, MIN_MS = 500, MAX_MS = 30000;

  const panel = document.createElement("div");
  panel.id = "radioPanel";
  panel.hidden = true;
  panel.innerHTML = `
    <div class="rhead"><b>📻 Radio</b><span class="meta" id="rState">off</span><button class="ghost" id="rClose">✕</button></div>
    <div class="rrow"><label>From radio <select id="rIn"></select></label><button id="rListen">Listen</button></div>
    <div class="rrow"><label>To radio <select id="rOut"></select></label>
      <label class="meta"><input type="checkbox" id="rAuto"> send replies without asking</label></div>
    <div class="rrow"><div class="rmeter"><i id="rLevel"></i></div><label class="meta">or <input type="file" id="rFile" accept="audio/*"> a recording</label></div>
    <div id="rLog"></div>`;
  document.body.appendChild(panel);

  async function devices() {
    try {
      const d = await navigator.mediaDevices.enumerateDevices();
      const fill = (sel, kind) => {
        const keep = sel.value;
        sel.innerHTML = d.filter((x) => x.kind === kind)
          .map((x, i) => `<option value="${esc(x.deviceId)}">${esc(x.label || kind + " " + (i + 1))}</option>`).join("");
        if (keep) sel.value = keep;
      };
      fill($("rIn"), "audioinput");
      fill($("rOut"), "audiooutput");
    } catch (e) { /* no permission yet */ }
  }

  function state(t) { $("rState").textContent = t; }

  // ------------------------------------------------------------ listening (voice activity)
  async function start() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { deviceId: $("rIn").value ? { exact: $("rIn").value } : undefined,
      echoCancellation: false, noiseSuppression: false, autoGainControl: false } });
    await devices();                                   // labels appear once allowed
    ctx = new AudioContext();
    src = ctx.createMediaStreamSource(stream);
    proc = ctx.createScriptProcessor(4096, 1, 1);
    src.connect(proc);
    proc.connect(ctx.destination);
    proc.onaudioprocess = (e) => {
      const x = e.inputBuffer.getChannelData(0);
      let s = 0;
      for (let i = 0; i < x.length; i++) s += x[i] * x[i];
      const rms = Math.sqrt(s / x.length), ms = (x.length / ctx.sampleRate) * 1000;
      $("rLevel").style.width = Math.min(100, rms * 600) + "%";
      if (sending) return;                             // don't hear our own reply
      const loud = rms > Math.max(0.01, floor * 4);
      if (!speaking) {
        floor = 0.995 * floor + 0.005 * rms;           // radio hiss level when nobody talks
        if (loud) { speaking = true; buf = [new Float32Array(x)]; quietMs = 0; startedAt = performance.now(); state("receiving…"); }
        return;
      }
      buf.push(new Float32Array(x));
      quietMs = loud ? 0 : quietMs + ms;
      const dur = performance.now() - startedAt;
      if (quietMs > HANG_MS || dur > MAX_MS) {
        speaking = false;
        const n = buf.reduce((a, b) => a + b.length, 0);
        if ((n / ctx.sampleRate) * 1000 >= MIN_MS) send(merge(buf, n), ctx.sampleRate);
        buf = [];
        state("listening");
      }
    };
    on = true;
    $("rListen").textContent = "Stop";
    $("rListen").classList.add("on");
    state("listening");
  }
  function stop() {
    on = false;
    try { proc && proc.disconnect(); src && src.disconnect(); stream && stream.getTracks().forEach((t) => t.stop()); ctx && ctx.close(); } catch (e) { /* closed */ }
    $("rListen").textContent = "Listen";
    $("rListen").classList.remove("on");
    state("off");
  }
  function merge(parts, n) { const o = new Float32Array(n); let k = 0; for (const p of parts) { o.set(p, k); k += p.length; } return o; }
  function wav(samples, sr) {
    const b = new ArrayBuffer(44 + samples.length * 2), v = new DataView(b);
    const w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
    w(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); w(8, "WAVE"); w(12, "fmt ");
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, sr, true);
    v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data");
    v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, samples[i])) * 32767, true);
    return new Blob([b], { type: "audio/wav" });
  }

  // ------------------------------------------------------------ one transmission
  async function send(samples, sr) { return post(wav(samples, sr)); }
  async function post(blob) {
    const fd = new FormData();
    fd.append("audio", blob, "radio.wav");
    const row = document.createElement("div");
    row.className = "rmsg";
    row.innerHTML = `<span class="meta">${new Date().toLocaleTimeString("fr-FR")}</span> analysing…`;
    $("rLog").prepend(row);
    try {
      const r = await fetch("/api/radio", { method: "POST", body: fd });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || r.statusText);
      show(row, d);
    } catch (e) { row.innerHTML += ` <span class="bad">${esc(e.message)}</span>`; }
  }
  function show(row, d) {
    const pk = (d.packets || []).map((p) => `<span class="chip">data packet: ${Object.keys(p).filter((k) => !["callsign", "minute", "seq"].includes(k)).join(", ")}</span>`).join("");
    const th = (d.threats || []).map((t) => `<span class="chip bad">${esc(t.class.replace("_", " "))} ${t.score}</span>`).join("");
    row.innerHTML = `<span class="meta">${new Date().toLocaleTimeString("fr-FR")}</span>
      <b>${esc(d.callsign || "?")}</b> → ${esc(d.report_id || "no report")}
      <div>${d.transcript ? "“" + esc(d.transcript) + "”" : '<span class="meta">no speech</span>'}</div>
      <div>${pk}${th}</div>${(d.notes || []).map((n) => `<div class="meta">${esc(n)}</div>`).join("")}`;
    if (d.reply) {
      const box = document.createElement("div");
      box.className = "rreply";
      box.innerHTML = `<textarea rows="3">${esc(d.reply)}</textarea>
        <div><button class="say">Send by voice</button>${d.field && d.field.guide ? '<button class="ghost tones">Send route tones</button>' : ""}<button class="ghost skip">Skip</button></div>`;
      row.appendChild(box);
      const lang = (d.field && d.field.lang) || "en";
      box.querySelector(".say").onclick = () => say(box.querySelector("textarea").value, lang, box);
      box.querySelector(".skip").onclick = () => box.remove();
      const t = box.querySelector(".tones");
      if (t) t.onclick = () => playUrl(`/api/report/${d.report_id}/route_tones.wav`, t);
      if ($("rAuto").checked) say(d.reply, lang, box);
    }
  }

  // ------------------------------------------------------------ talking back into the radio
  async function say(text, lang, box) {
    const r = await fetch("/api/tts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }) });
    if (!r.ok) {                                       // no offline voice: the browser one, default speaker
      if ("speechSynthesis" in window) { const u = new SpeechSynthesisUtterance(text); u.lang = lang === "fr" ? "fr-FR" : "en-GB"; speechSynthesis.speak(u); }
      return;
    }
    await playBlob(await r.blob());
    if (box) box.innerHTML = `<span class="meta">sent: ${esc(text)}</span>`;
  }
  async function playUrl(url, btn) { const r = await fetch(url); if (r.ok) { await playBlob(await r.blob()); if (btn) btn.textContent = "route sent"; } }
  async function playBlob(blob) {
    const a = new Audio(URL.createObjectURL(blob));
    try { if ($("rOut").value && a.setSinkId) await a.setSinkId($("rOut").value); } catch (e) { /* default output */ }
    sending = true;
    state("transmitting… (press the radio's PTT, or use VOX)");
    await a.play().catch(() => {});
    await new Promise((res) => { a.onended = res; a.onerror = res; });
    setTimeout(() => { sending = false; state(on ? "listening" : "off"); }, 400);
  }

  $("rListen").onclick = () => (on ? stop() : start().catch((e) => state("no input: " + e.message)));
  $("rClose").onclick = () => { panel.hidden = true; };
  $("rFile").onchange = (e) => { const f = e.target.files[0]; if (f) post(f); e.target.value = ""; };
  navigator.mediaDevices && navigator.mediaDevices.addEventListener && navigator.mediaDevices.addEventListener("devicechange", devices);
  devices();
  return { toggle: () => { panel.hidden = !panel.hidden; if (!panel.hidden) devices(); }, post, say };
})();
