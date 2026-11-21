// Scene reconstruction panel: "what we guess the place looks like" next to
// "what the place really looks like" at each candidate area (backend/scene.py).
//
// Plain canvas, oblique 3D projection, painter's algorithm. Frame of every scene:
// observer at (0,0), +y = 12 o'clock (ahead), +x = 3 o'clock, z = up, metres.
// Drag a view to turn both views together.

const Scene3D = (() => {
  const C = {
    ground: "#18201d", ring: "#2a3531", text: "#e6ece9", muted: "#8b9a94",
    guess: "232,197,71", real: "#3b4a45", roof: "#5b6b65", obs: "#33e1ff",
    rail: "#b9b2a6", road: "#59615e", water: "#3b7bbf", tree: "#2f7a4c",
  };
  const LM_COLOR = { keep: "#e8c547", castle: "#e8c547", castle_tower: "#e8c547", church: "#c9a0ff",
                     tower: "#ff8c5a", water_tower: "#5ac8ff", station: "#4cc38a" };

  function projector(cv, scene, view) {
    const W = cv.width, H = cv.height, R = scene.radius;
    const s = (Math.min(W, H * 1.6) * 0.44) / R;
    const cy = H * 0.6, cx = W / 2;
    const cyaw = Math.cos(view.yaw), syaw = Math.sin(view.yaw);
    const se = Math.sin(view.elev), ce = Math.cos(view.elev);
    return {
      s, R,
      p(x, y, z = 0) {
        const xr = x * cyaw - y * syaw, yr = x * syaw + y * cyaw;
        return [cx + xr * s, cy - yr * s * se - z * s * ce, yr];
      },
    };
  }

  function polar(beta, r) { const b = (beta * Math.PI) / 180; return [r * Math.sin(b), r * Math.cos(b)]; }

  function draw(cv, scene, view, title) {
    const g = cv.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const cw = cv.clientWidth, ch = cv.clientHeight;
    if (cv.width !== cw * dpr) { cv.width = cw * dpr; cv.height = ch * dpr; }
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    const P = projector({ width: cw, height: ch }, scene, view);
    const R = P.R;
    g.clearRect(0, 0, cw, ch);
    const sky = g.createLinearGradient(0, 0, 0, ch);
    sky.addColorStop(0, "#101716"); sky.addColorStop(1, "#0b0e0d");
    g.fillStyle = sky; g.fillRect(0, 0, cw, ch);

    // Ground disk + range rings.
    const ring = (r, fill, stroke, dash) => {
      g.beginPath();
      for (let a = 0; a <= 64; a++) {
        const [x, y] = polar(a * 360 / 64, r), q = P.p(x, y);
        a ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]);
      }
      if (fill) { g.fillStyle = fill; g.fill(); }
      if (stroke) { g.setLineDash(dash || []); g.strokeStyle = stroke; g.stroke(); g.setLineDash([]); }
    };
    ring(R, C.ground, C.ring);
    const step = R > 60 ? 50 : R > 25 ? 10 : 5;
    g.font = "10px system-ui"; g.fillStyle = C.muted;
    for (let r = step; r < R; r += step) {
      ring(r, null, C.ring, [2, 4]);
      const q = P.p(...polar(135, r));
      g.fillText(`${r} m`, q[0] + 2, q[1]);
    }

    // Lines on the ground: rail, road, water.
    for (const st of scene.strips || []) {
      const col = C[st.kind] || C.road;
      if (st.dots) {                 // real: sampled points of the line
        for (const [x, y] of st.pts) {
          if (Math.hypot(x, y) > R) continue;
          const q = P.p(x, y);
          g.fillStyle = col; g.beginPath(); g.arc(q[0], q[1], Math.max(2, st.w * P.s * 0.3), 0, 7); g.fill();
        }
      } else {                       // guessed: a strip, direction unknown
        g.beginPath();
        st.pts.forEach(([x, y], i) => { const q = P.p(x, y); i ? g.lineTo(q[0], q[1]) : g.moveTo(q[0], q[1]); });
        g.lineWidth = Math.max(2, st.w * P.s); g.strokeStyle = col; g.globalAlpha = 0.45;
        g.setLineDash(st.guess ? [8, 6] : []); g.stroke(); g.setLineDash([]); g.globalAlpha = 1; g.lineWidth = 1;
      }
    }

    // Spoken directions: a wedge of +-sigma (guessed view) or a dashed ray (real view).
    const said = scene.guess ? (scene.landmarks || []) : (scene.said || []);
    for (const d of said) {
      const col = `rgba(${C.guess},`;
      if (scene.guess) {
        g.beginPath(); const o = P.p(0, 0); g.moveTo(o[0], o[1]);
        for (let a = -d.sigma; a <= d.sigma; a += 3) { const q = P.p(...polar(d.beta + a, R)); g.lineTo(q[0], q[1]); }
        g.closePath(); g.fillStyle = col + (d.heard ? "0.06)" : "0.10)"); g.fill();
      } else {
        const o = P.p(0, 0), q = P.p(...polar(d.beta, R));
        g.setLineDash([5, 5]); g.strokeStyle = col + "0.7)"; g.beginPath(); g.moveTo(o[0], o[1]); g.lineTo(q[0], q[1]); g.stroke(); g.setLineDash([]);
      }
    }

    // 3D objects, far to near.
    const objs = [];
    for (const b of scene.buildings || []) {
      const cx = b.pts.reduce((a, p) => a + p[0], 0) / b.pts.length, cy = b.pts.reduce((a, p) => a + p[1], 0) / b.pts.length;
      objs.push({ d: P.p(cx, cy)[2], f: () => building(g, P, b, scene.guess) });
    }
    for (const rm of scene.rooms || []) objs.push({ d: 1e5, f: () => room(g, P, rm) });   // drawn last: we are inside
    for (const [x, y] of scene.trees || []) {
      if (Math.hypot(x, y) > R) continue;
      objs.push({ d: P.p(x, y)[2], f: () => tree(g, P, x, y, scene.guess) });
    }
    for (const lm of scene.landmarks || []) {
      const r = Math.min(lm.dist, R * 0.96), [x, y] = polar(lm.beta, r);
      objs.push({ d: P.p(x, y)[2], f: () => landmark(g, P, lm, x, y, scene.guess) });
    }
    objs.push({ d: 0, f: () => observer(g, P) });
    objs.sort((a, b) => b.d - a.d).forEach((o) => o.f());

    // Sun in the sky, at its clock direction.
    if (scene.sun) {
      const [x, y] = polar(scene.sun.beta, R * 1.05);
      const z = Math.min(R * Math.tan((scene.sun.elev * Math.PI) / 180), R * 0.7);
      const q = P.p(x, y, z);
      g.fillStyle = "#ffd54a"; g.shadowColor = "#ffd54a"; g.shadowBlur = 12;
      g.beginPath(); g.arc(q[0], q[1], 7, 0, 7); g.fill(); g.shadowBlur = 0;
      g.fillStyle = C.muted; g.fillText("sun", q[0] + 9, q[1] + 3);
    }
    // North (only known on a real area: heading comes from the localiser).
    if (scene.heading != null) {
      const q = P.p(...polar(-scene.heading, R * 1.02));
      g.fillStyle = "#e5484d"; g.font = "bold 12px system-ui"; g.fillText("N", q[0] - 4, q[1] + 4);
    }

    g.font = "600 12px system-ui"; g.fillStyle = C.text; g.fillText(title, 10, 18);
    if (scene.setting) { g.font = "11px system-ui"; g.fillStyle = C.muted; g.fillText(scene.setting.label, 10, 33); }
  }

  function building(g, P, b, guess) {
    const pts = b.pts, h = b.h;
    const walls = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], c = pts[(i + 1) % pts.length];
      walls.push({ a, c, d: P.p((a[0] + c[0]) / 2, (a[1] + c[1]) / 2)[2] });
    }
    walls.sort((x, y) => y.d - x.d);
    const alpha = b.shell ? 0.05 : 0.16;
    for (const w of walls) {
      const q = [P.p(w.a[0], w.a[1]), P.p(w.c[0], w.c[1]), P.p(w.c[0], w.c[1], h), P.p(w.a[0], w.a[1], h)];
      g.beginPath(); q.forEach((v, i) => (i ? g.lineTo(v[0], v[1]) : g.moveTo(v[0], v[1]))); g.closePath();
      if (guess) {
        g.fillStyle = `rgba(${C.guess},${alpha})`; g.fill();
        g.setLineDash([3, 3]); g.strokeStyle = `rgba(${C.guess},${b.shell ? 0.25 : 0.55})`; g.stroke(); g.setLineDash([]);
      } else {
        // Shade by wall orientation, so the volume reads.
        const ang = Math.atan2(w.c[1] - w.a[1], w.c[0] - w.a[0]);
        const l = 0.75 + 0.25 * Math.cos(ang * 2);
        g.fillStyle = shade(C.real, l); g.fill(); g.strokeStyle = "#0e1312"; g.stroke();
      }
    }
    g.beginPath();
    pts.forEach((p, i) => { const v = P.p(p[0], p[1], h); i ? g.lineTo(v[0], v[1]) : g.moveTo(v[0], v[1]); });
    g.closePath();
    if (guess) { g.fillStyle = `rgba(${C.guess},${alpha + 0.06})`; g.fill(); }
    else { g.fillStyle = C.roof; g.fill(); g.strokeStyle = "#0e1312"; g.stroke(); }
  }

  function room(g, P, rm) {
    const h = rm.h;
    g.strokeStyle = "rgba(51,225,255,.8)"; g.fillStyle = "rgba(51,225,255,.06)";
    const loop = (z) => { g.beginPath(); rm.pts.forEach((p, i) => { const v = P.p(p[0], p[1], z); i ? g.lineTo(v[0], v[1]) : g.moveTo(v[0], v[1]); }); g.closePath(); };
    loop(0); g.fill(); g.stroke(); loop(h); g.stroke();
    for (const p of rm.pts) { const a = P.p(p[0], p[1]), b = P.p(p[0], p[1], h); g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); }
  }

  function tree(g, P, x, y, guess) {
    const a = P.p(x, y), b = P.p(x, y, 7);
    g.strokeStyle = "#4a3b2a"; g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke();
    g.fillStyle = guess ? "rgba(47,122,76,.55)" : C.tree;
    g.beginPath(); g.arc(b[0], b[1], Math.max(2.5, 3.5 * P.s), 0, 7); g.fill();
  }

  function landmark(g, P, lm, x, y, guess) {
    const col = LM_COLOR[lm.type] || "#e6ece9";
    const z = Math.min(lm.h, P.R * 0.45);
    const a = P.p(x, y), b = P.p(x, y, z);
    g.lineWidth = 3; g.strokeStyle = col; g.globalAlpha = guess ? 0.6 : 1;
    g.setLineDash(guess ? [4, 3] : []);
    g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); g.setLineDash([]); g.lineWidth = 1;
    g.fillStyle = col; g.beginPath(); g.arc(b[0], b[1], 4, 0, 7); g.fill(); g.globalAlpha = 1;
    const far = lm.dist > P.R ? ` → ${Math.round(lm.dist)} m` : "";
    const dist = guess && !lm.dist_said ? " (dist?)" : far;
    g.font = "11px system-ui"; g.fillStyle = col;
    g.fillText(`${lm.label}${dist}`, b[0] + 6, b[1] - 2);
  }

  function observer(g, P) {
    const o = P.p(0, 0), f = P.p(0, P.R * 0.18);
    g.strokeStyle = C.obs; g.fillStyle = C.obs; g.lineWidth = 2;
    g.beginPath(); g.moveTo(o[0], o[1]); g.lineTo(f[0], f[1]); g.stroke(); g.lineWidth = 1;
    g.beginPath(); g.arc(o[0], o[1], 5, 0, 7); g.fill();
    g.font = "10px system-ui"; g.fillText("12", f[0] + 4, f[1]);
  }

  function shade(hex, k) {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.min(255, Math.round(v * k)));
    return `rgb(${c[0]},${c[1]},${c[2]})`;
  }

  return { draw };
})();

// ------------------------------------------------------------------ panel
const ScenePanel = (() => {
  const view = { yaw: 0.45, elev: 0.6, auto: true };
  let data = null, pick = 0, key = null, busy = false, open = true;
  const el = document.getElementById("scene");
  if (!el) return { show() {} };      // page without the floating panel (pipeline.html)
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  async function show(rep) {
    const has = rep && (rep.position || Object.keys(rep.evidence || {}).length);
    if (!has) { el.hidden = true; data = null; key = null; return; }
    el.hidden = false;
    const k = rep.id + ":" + rep.updated_ms;
    if (k === key || busy) return;
    busy = true;
    try {
      const r = await fetch(`/api/report/${rep.id}/scene`);
      if (r.ok) {
        const d = await r.json();
        if (!data || data.report_id !== d.report_id) pick = 0;
        data = d; key = k;
        if (pick >= data.candidates.length) pick = 0;
        layout();
      }
    } finally { busy = false; }
  }

  function layout() {
    if (!data) return;
    const tabs = data.candidates.map((c, i) => `<button data-i="${i}" class="${i === pick ? "on" : ""}">
        Area ${c.label} · ${Math.round(c.mass * 100)}%${c.fit != null ? ` <small>fit ${Math.round(c.fit * 100)}%</small>` : ""}</button>`).join("");
    const e = data.estimate, c = data.candidates[pick];
    const notes = (e.notes || []).map((n) => `<li>${esc(n)}</li>`).join("");
    const lms = (e.landmarks || []).map((l) => `<li><b>${esc(l.label)}</b> ${esc(l.text)}${l.heard ? " (heard)" : ""}</li>`).join("");
    const snd = (e.sounds || []).filter((s) => s.heard).map((s) => esc(s.label)).join(", ");
    const checks = c ? c.checks.map((k) => {
      const cls = k.score >= 0.6 ? "ok" : k.score >= 0.3 ? "mid" : "bad";
      return `<li class="${cls}"><i>${k.score >= 0.6 ? "✓" : k.score >= 0.3 ? "~" : "✗"}</i><b>${esc(k.label)}</b> ${esc(k.text)}</li>`;
    }).join("") : "";
    el.innerHTML = `<div class="shead">
        <div class="label">Scene reconstruction · ${esc(data.report_id)} <span class="meta">approximate · drag to turn</span></div>
        <div class="tabs">${tabs}</div>
        <button id="sceneMin" class="ghost" title="Hide / show">${open ? "–" : "+"}</button></div>
      <div class="sbody" ${open ? "" : "hidden"}>
        <div class="col"><canvas id="cvGuess"></canvas>
          <ul class="snotes">${notes}${lms}${snd ? `<li>hears: ${snd}</li>` : ""}</ul></div>
        <div class="col"><canvas id="cvReal"></canvas>
          ${c ? `<ul class="schecks">${checks}</ul>` : `<div class="meta">No candidate area yet.</div>`}</div>
      </div>`;
    el.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => {
      pick = Number(b.dataset.i); layout();
      const cc = data.candidates[pick];
      if (cc && typeof map !== "undefined") map.panTo([cc.lat, cc.lon]);   // the Leaflet map (map.js)
    }));
    document.getElementById("sceneMin").onclick = () => { open = !open; layout(); };
    for (const id of ["cvGuess", "cvReal"]) drag(document.getElementById(id));
    paint();
  }

  function paint() {
    if (!data || el.hidden || !open) return;
    const g = document.getElementById("cvGuess"), r = document.getElementById("cvReal");
    if (!g) return;
    Scene3D.draw(g, data.estimate, view, "Guessed from the report");
    const c = data.candidates[pick];
    if (c) Scene3D.draw(r, { ...c.scene, heading: c.heading }, view, `Real surroundings · area ${c.label}`);
    else r.getContext("2d").clearRect(0, 0, r.width, r.height);
  }

  function drag(cv) {
    if (!cv) return;
    let x0 = null, y0 = null;
    cv.onpointerdown = (e) => { x0 = e.clientX; y0 = e.clientY; view.auto = false; cv.setPointerCapture(e.pointerId); };
    cv.onpointermove = (e) => {
      if (x0 == null) return;
      view.yaw += (e.clientX - x0) * 0.01;
      view.elev = Math.min(1.45, Math.max(0.2, view.elev + (e.clientY - y0) * 0.005));
      x0 = e.clientX; y0 = e.clientY; paint();
    };
    cv.onpointerup = () => { x0 = null; };
    cv.ondblclick = () => { view.yaw = 0.45; view.elev = 0.6; view.auto = true; };
  }

  // Slow turn until the user grabs a view: it reads as 3D at a glance.
  (function tick(t) {
    if (view.auto && data && open && !el.hidden) { view.yaw = 0.45 + Math.sin(t / 6000) * 0.4; paint(); }
    requestAnimationFrame(tick);
  })(performance.now());
  window.addEventListener("resize", paint);

  return { show };
})();
