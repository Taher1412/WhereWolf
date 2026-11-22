// Shared report panels, used by the coordinator page (/map, in tabs) and the
// step-by-step demo page (/pipeline). Each panel draws into fixed element ids if
// they exist on the page:
//   Sound      #cues (what the audio measured, bits per cue) · #spec #specMeta #lanes #echo #space
//   Location   #measured (echo rings) · #place (real buildings at an area) · #cands #checks
//   Body       (body3d.js)     Response  #impact #bring (impact.js)
// Panels.load(rep) fetches /viz, /surround, /body, /response for a report and draws all.
// Panels.onCandidates(cs, pick, rep) / onSurround(s, rep): hooks for the page's map.

const Panels = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const GROUP_COLOR = { speech: "#8b9a94", rail: "#b9b2a6", traffic: "#f0a33a", bells: "#c9a0ff",
                        machinery: "#ff6b5a", nature: "#4cc38a", aircraft: "#5ac8ff", siren: "#e5484d", crowd: "#e6ece9" };
  const SPACE_NAMES = { indoor_small: "indoors · small room", indoor_large: "indoors · large hall",
                        outdoor_enclosed: "outdoors · between buildings", outdoor_open: "outdoors · open ground" };
  const P = { viz: null, surround: null, body: null, response: null, pick: 0, key: null, onCandidates: null, onSurround: null };

  // ---------------------------------------------------------------- canvas helpers
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
    if (!cv) return;
    const [g, w, h] = ctx(cv);
    g.fillStyle = "#8b9a94"; g.font = "12px system-ui"; g.textAlign = "center";
    // Wrap to the canvas width (small tiles).
    const lines = [];
    for (const word of text.split(" ")) {
      const last = lines[lines.length - 1];
      if (last && g.measureText(last + " " + word).width < w - 16) lines[lines.length - 1] = last + " " + word;
      else lines.push(word);
    }
    lines.forEach((l, i) => g.fillText(l, w / 2, h / 2 + (i - (lines.length - 1) / 2) * 15));
    g.textAlign = "left";
  }
  const visible = (el) => el && el.offsetParent !== null && el.clientWidth > 0;

  const LUT = (() => {   // inferno-like colour map
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
  const ML = 74;
  const mel = (f) => 2595 * Math.log10(1 + f / 700);

  // ---------------------------------------------------------------- sound
  function drawSpec() {
    const cv = $("spec");
    if (!visible(cv)) return;
    const viz = P.viz;
    if (!viz || !viz.spec) { emptyMsg(cv, "No audio yet: press Listen on the field phone, or Simulate listen."); if ($("specMeta")) $("specMeta").textContent = ""; return; }
    const sp = viz.spec;
    if ($("specMeta")) $("specMeta").textContent = `· ${viz.simulated ? "SIMULATED clip · " : ""}${viz.kind || ""} · ${sp.dur_s} s`;
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
    g.fillStyle = "#8b9a94"; g.strokeStyle = "rgba(255,255,255,.12)";
    const m0 = mel(sp.fmin), m1 = mel(sp.fmax);
    for (const f of [100, 250, 500, 1000, 2000, 4000, 8000]) {
      if (f > sp.fmax) continue;
      const y = ph * (1 - (mel(f) - m0) / (m1 - m0));
      g.fillText(f >= 1000 ? `${f / 1000} kHz` : `${f} Hz`, ML - 44, Math.max(y + 3, 9));
      g.beginPath(); g.moveTo(ML, y); g.lineTo(ML + pw, y); g.stroke();
    }
    for (let t = 0; t <= sp.dur_s; t += 1) g.fillText(`${t}s`, X(t) - 4, h - 3);
    if (viz.chirp) {
      const [a, b] = viz.chirp;
      g.strokeStyle = "#33e1ff"; g.setLineDash([4, 3]); g.strokeRect(X(a), 1, X(b) - X(a), ph - 2); g.setLineDash([]);
      g.fillStyle = "#33e1ff"; g.fillText("chirp", X(a) + 3, 12);
    }
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
    if (!visible(cv)) return;
    const tl = P.viz && P.viz.timeline, dur = P.viz && P.viz.spec && P.viz.spec.dur_s;
    if (!tl || !dur) { ctx(cv); return; }
    const groups = Object.keys(tl.groups).filter((k) => k === "speech" || Math.max(...tl.groups[k]) >= 0.05);
    for (const k of ["rail", "traffic", "bells", "machinery", "nature"]) if (!groups.includes(k) && tl.groups[k]) groups.push(k);
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
    if (!visible(cv)) return;
    const viz = P.viz, eg = viz && viz.echogram;
    if (!eg) { emptyMsg(cv, viz ? "No chirp in this clip (Listen with the chirp on)." : ""); return; }
    const [g, w, h] = ctx(cv);
    const L = 30, B = 16, pw = w - L - 8, ph = h - B - 6, maxD = eg.db.length * eg.step_m;
    const X = (d) => L + (d / maxD) * pw, Y = (db) => 4 + ph * (Math.max(-60, Math.min(0, db)) / -60);
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
    const host = $("space");
    if (!host) return;
    const a = rep && (rep.acoustic || [])[rep.acoustic.length - 1];
    if (!a) { host.innerHTML = `<div class="muted">No clip analysed yet.</div>`; return; }
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
    host.innerHTML = `${bars || `<div class="muted">No spatial clue in this clip.</div>`}
      ${nums.length ? `<div class="meta">${esc(nums.join(" · "))}</div>` : ""}
      ${(sp.clues || []).length ? `<div class="meta">clues: ${esc(sp.clues.join("; "))}</div>` : ""}
      <div class="chips">${chips}</div>${alerts}
      <div class="meta">${esc(a.quality || "")} clip${(a.notes || []).length ? " · " + esc(a.notes.join("; ")) : ""}</div>`;
  }

  // ---------------------------------------------------------------- what the audio says
  // One row per measurement, with how much it narrowed the map (bits, from a flat prior).
  const CUE_OF = { echoes: "echoes", ambient: "ambient", setting: "space", hear: "sounds" };
  function renderCues() {
    const host = $("cues");
    if (!host) return;
    const s = P.surround, m = s && s.measured;
    if (P.sMissing) {
      host.innerHTML = `<div class="muted">This server has no surroundings matching: it was started before the update. Restart it (Ctrl+C, <code>python run.py</code>).</div>`;
      return;
    }
    if (P.sWait && !s) {
      host.innerHTML = `<div class="muted">Matching the measurements against the real buildings…</div>`;
      return;
    }
    if (!s || !m) {
      host.innerHTML = `<div class="muted">No audio yet. Each push-to-talk report is analysed (voice level, background, echoes of the end chirp). <b>Listen</b> adds a quiet clip.</div>`;
      return;
    }
    const bits = {};
    (s.cues || []).filter((c) => c.source !== "voice").forEach((c) => { const k = CUE_OF[c.kind]; bits[k] = (bits[k] || 0) + c.bits; });
    const bar = (k) => bits[k] != null
      ? `<span class="bits" title="how much this cue alone narrowed the map"><i style="width:${Math.min(100, (bits[k] / 1.5) * 100)}%"></i><em>${bits[k].toFixed(2)} bits</em></span>`
      : `<span class="bits off"><em>not used</em></span>`;
    const rows = [];
    const ech = m.echoes.length ? m.echoes.map((e) => e.m.toFixed(1)).join(" · ") + " m" : m.probe_ok ? "none within 25 m" : "–";
    rows.push(["Echoes", ech, m.probe_ok ? m.echo_status : "no chirp heard in this clip", "echoes"]);
    const a = m.ambient;
    rows.push(["Background", a ? `${Math.round(a.dba)} dB(A) ±${Math.round(a.sigma)}` : "–",
               a ? `${a.label} · reference: ${a.ref}${a.note ? " · " + a.note : ""}` : "", "ambient"]);
    const sp = m.space;
    rows.push(["Space", sp ? `${sp.label} ${Math.round(sp.p_best * 100)}%` : "–",
               [m.rt60_s ? `reverberation ${m.rt60_s} s` : "", m.drr_db != null ? `direct/reverb ${m.drr_db} dB` : ""].filter(Boolean).join(" · "), "space"]);
    const snd = m.sounds.filter((x) => x.score >= 0.1);
    rows.push(["Sounds", snd.length ? snd.map((x) => `${x.cls} ${x.score.toFixed(2)}`).join(" · ") : "nothing clear",
               snd.some((x) => x.under_speech) ? "heard under the voice (half weight)" : "", "sounds"]);
    const ao = s.audio_only;
    host.innerHTML = `${m.simulated ? `<div class="simflag">SIMULATED clip, built from the real place at the true spot</div>` : ""}
      ${rows.map(([k, v, sub, key]) => `<div class="cue"><b>${k}</b><span class="v">${esc(v)}</span>${bar(key)}<small>${esc(sub)}</small></div>`).join("")}
      ${ao ? `<div class="aonly">Audio alone: 90% of the probability in <b>${ao.km2_90} km²</b> (${Math.round(ao.share * 100)}% of the map, ${ao.bits.toFixed(2)} bits). It narrows the <i>kind</i> of spot; landmarks or one question give the place.</div>` : ""}`;
  }

  // ---------------------------------------------------------------- location
  function renderCands(rep) {
    const cs = (P.surround && P.surround.candidates) || [];
    const host = $("cands");
    if (P.pick >= cs.length) P.pick = 0;
    if (host) {
      host.innerHTML = cs.length ? cs.map((c, i) => `<div class="cand ${i === P.pick ? "on" : ""}" data-i="${i}">
          <b>Area ${c.label}</b><div class="bar"><i style="width:${Math.round(c.mass * 100)}%"></i></div>
          <small>${Math.round(c.mass * 100)}% · fit ${c.fit != null ? Math.round(c.fit * 100) + "%" : "–"}</small></div>`).join("")
        : `<div class="muted">No candidate area yet.</div>`;
      host.querySelectorAll(".cand").forEach((el) => (el.onclick = () => { P.pick = Number(el.dataset.i); renderCands(rep); paintPlaces(); }));
    }
    if ($("checks")) {
      const c = cs[P.pick];
      $("checks").innerHTML = c ? c.checks.map((k) => {
        const cls = k.score >= 0.6 ? "ok" : k.score >= 0.3 ? "mid" : "bad";
        return `<li class="${cls}"><i>${k.score >= 0.6 ? "✓" : k.score >= 0.3 ? "~" : "✗"}</i><b>${esc(k.label)}</b> ${esc(k.text)}</li>`;
      }).join("") : "";
    }
    if (P.onCandidates) P.onCandidates(cs, P.pick, rep || {});
  }
  function paintPlaces() {
    const m = P.surround && P.surround.measured;
    if (visible($("measured"))) Surround.measured($("measured"), m);
    if (visible($("place"))) Surround.place($("place"), P.surround && P.surround.candidates[P.pick], m);
  }

  // ---------------------------------------------------------------- data
  const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);

  async function load(rep) {
    if (!rep) { clear(); return; }
    P.rep = rep;
    renderSpace(rep);
    const key = rep.id + ":" + rep.updated_ms;
    if (key === P.key) return;
    P.key = key;
    // The surroundings match is the slowest call: draw the rest as soon as it is in.
    // 404 = a server started before the surroundings code existed.
    const sP = fetch(`/api/report/${rep.id}/surround`)
      .then((r) => (r.ok ? r.json() : r.status === 404 ? "missing" : null)).catch(() => null);
    P.sWait = true;
    const [v, b, resp] = await Promise.all([get(`/api/report/${rep.id}/viz`), get(`/api/report/${rep.id}/body`),
                                           get(`/api/report/${rep.id}/response`)]);
    if (P.key !== key) return;          // a newer update arrived meanwhile
    P.viz = v && v.spec ? v : null; P.body = b; P.response = resp;
    if (window.Body3D) window.Body3D.show(b); else window.__pendingTwin = b;   // body3d.js is a module
    if (typeof Impact !== "undefined") { Impact.showBody(b); Impact.show(resp); }   // const in impact.js: not on window
    drawSpec(); drawLanes(); drawEcho(); renderCues();
    let s = await sP;
    if (P.key !== key) return;
    P.sWait = false; P.sMissing = s === "missing";
    if (P.sMissing) s = null;
    if (!P.surround || !s || P.surround.report_id !== s.report_id) P.pick = 0;
    P.surround = s;
    if (P.onSurround) P.onSurround(s, rep);
    redraw(rep);
  }
  function clear() {
    P.viz = P.surround = P.body = P.response = null; P.key = null; P.rep = null;
    if (typeof Impact !== "undefined") { Impact.showBody(null); Impact.show(null); }
    ["space", "checks", "cands", "cues"].forEach((id) => $(id) && ($(id).innerHTML = ""));
    if (P.onSurround) P.onSurround(null, null);
    redraw(null);
  }
  // Redraw everything visible (after a tile is enlarged or a resize).
  function redraw(rep = P.rep) {
    drawSpec(); drawLanes(); drawEcho();
    renderCues(); renderCands(rep); paintPlaces();
  }

  window.addEventListener("resize", () => redraw());
  return { load, redraw, renderSpace, state: P,
           set onCandidates(f) { P.onCandidates = f; }, set onSurround(f) { P.onSurround = f; } };
})();
