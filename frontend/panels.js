// Shared report panels, used by the coordinator page (/map, in tabs) and the
// step-by-step demo page (/pipeline). Each panel draws into fixed element ids if
// they exist on the page:
//   Sound      #spec #specMeta #lanes #echo #space
//   Location   #guess #guessNotes #real #cands #checks
//   Body       (body3d.js)     Response  #impact #bring (impact.js)
// Panels.load(rep) fetches /viz, /scene, /body, /response for a report and draws all.
// Panels.onCandidates(cs, pick, rep) is called so the page can show the areas on its map.

const Panels = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const GROUP_COLOR = { speech: "#8b9a94", rail: "#b9b2a6", traffic: "#f0a33a", bells: "#c9a0ff",
                        machinery: "#ff6b5a", nature: "#4cc38a", aircraft: "#5ac8ff", siren: "#e5484d", crowd: "#e6ece9" };
  const SPACE_NAMES = { indoor_small: "indoors · small room", indoor_large: "indoors · large hall",
                        outdoor_enclosed: "outdoors · between buildings", outdoor_open: "outdoors · open ground" };
  const view = { yaw: 0.45, elev: 0.6, auto: true };
  const P = { viz: null, scene: null, body: null, response: null, pick: 0, key: null, onCandidates: null };

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

  // ---------------------------------------------------------------- location
  function tagOf(n) {
    if (/assumed|typical|unknown/.test(n)) return "assumed";
    if (/chirp|reverberation/.test(n)) return "measured";
    return "inferred";
  }
  function renderGuessNotes() {
    const host = $("guessNotes");
    if (!host) return;
    const e = P.scene && P.scene.estimate;
    if (!e) { host.innerHTML = ""; return; }
    const items = [`<li><span class="tag">space</span><b>${esc(e.setting.label)}</b></li>`];
    for (const l of e.landmarks) items.push(`<li><span class="tag">${l.heard ? "heard" : "said"}</span><b>${esc(l.label)}</b> ${esc(l.text)}</li>`);
    if (e.sun) items.push(`<li><span class="tag">said</span><b>sun</b> ${Math.round(e.sun.beta / 30) || 12} o'clock → gives the heading</li>`);
    for (const s of e.sounds) items.push(`<li><span class="tag">${s.source === "voice" ? "said" : "audio"}</span><b>${esc(s.label)}</b> ${s.heard ? "heard" : "not heard"}</li>`);
    for (const n of e.notes) items.push(`<li><span class="tag">${tagOf(n)}</span>${esc(n)}</li>`);
    host.innerHTML = items.join("");
  }
  function renderCands(rep) {
    const cs = (P.scene && P.scene.candidates) || [];
    const host = $("cands");
    if (P.pick >= cs.length) P.pick = 0;
    if (host) {
      host.innerHTML = cs.length ? cs.map((c, i) => `<div class="cand ${i === P.pick ? "on" : ""}" data-i="${i}">
          <b>Area ${c.label}</b><div class="bar"><i style="width:${Math.round(c.mass * 100)}%"></i></div>
          <small>${Math.round(c.mass * 100)}% · fit ${c.fit != null ? Math.round(c.fit * 100) + "%" : "–"}</small></div>`).join("")
        : `<div class="muted">No candidate area yet.</div>`;
      host.querySelectorAll(".cand").forEach((el) => (el.onclick = () => { P.pick = Number(el.dataset.i); renderCands(rep); paintScenes(); }));
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
  function paintScenes() {
    const g = $("guess"), r = $("real");
    if (visible(g)) {
      const e = P.scene && P.scene.estimate;
      if (e) Scene3D.draw(g, e, view, "Guessed from the report"); else emptyMsg(g, "Nothing described yet.");
    }
    if (visible(r)) {
      const c = P.scene && P.scene.candidates[P.pick];
      if (c) Scene3D.draw(r, { ...c.scene, heading: c.heading }, view, `Real surroundings · area ${c.label}`);
      else emptyMsg(r, "No candidate area yet.");
    }
  }
  function bindDrag() {
    for (const id of ["guess", "real"]) {
      const cv = $(id);
      if (!cv) continue;
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
  }
  let lastPaint = 0;
  (function tick(t) {
    if (view.auto && P.scene && t - lastPaint > 40) { view.yaw = 0.45 + Math.sin(t / 6000) * 0.4; paintScenes(); lastPaint = t; }
    requestAnimationFrame(tick);
  })(0);

  // ---------------------------------------------------------------- data
  const get = (u) => fetch(u).then((r) => (r.ok ? r.json() : null)).catch(() => null);

  async function load(rep) {
    if (!rep) { clear(); return; }
    P.rep = rep;
    renderSpace(rep);
    const key = rep.id + ":" + rep.updated_ms;
    if (key === P.key) return;
    P.key = key;
    const [v, s, b, resp] = await Promise.all([get(`/api/report/${rep.id}/viz`), get(`/api/report/${rep.id}/scene`),
                                                get(`/api/report/${rep.id}/body`), get(`/api/report/${rep.id}/response`)]);
    if (P.key !== key) return;          // a newer update arrived meanwhile
    if (!P.scene || !s || P.scene.report_id !== s.report_id) P.pick = 0;
    P.viz = v && v.spec ? v : null; P.scene = s; P.body = b; P.response = resp;
    if (window.Body3D) window.Body3D.show(b); else window.__pendingTwin = b;   // body3d.js is a module
    if (typeof Impact !== "undefined") Impact.show(resp);   // const in impact.js: not on window
    redraw(rep);
  }
  function clear() {
    P.viz = P.scene = P.body = P.response = null; P.key = null; P.rep = null;
    if (typeof Impact !== "undefined") Impact.show(null);
    ["space", "guessNotes", "checks", "cands"].forEach((id) => $(id) && ($(id).innerHTML = ""));
    redraw(null);
  }
  // Redraw everything visible (call after a tab becomes visible or a resize).
  function redraw(rep = P.rep) {
    drawSpec(); drawLanes(); drawEcho();
    renderGuessNotes(); renderCands(rep); paintScenes();
  }

  bindDrag();
  window.addEventListener("resize", () => redraw());
  return { load, redraw, renderSpace, state: P, set onCandidates(f) { P.onCandidates = f; } };
})();
