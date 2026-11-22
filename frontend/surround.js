// What the audio measured around the phone, and the real places it is compared with
// (backend/surround.py, /api/report/{id}/surround). Plain canvas, north up, true scale.
//
//   Surround.measured(canvas, m)   rings at the echo distances the chirp heard
//                                  (one mic = distance only: a ring, not a direction)
//   Surround.place(canvas, cand, m) real IGN footprints around the best-fitting spot of an
//                                  area, the free space seen from it (36 rays), the walls
//                                  that should echo (green = heard, grey = not heard), and
//                                  the measured rings on top: rings touching walls = a match.

const Surround = (() => {
  const CYAN = "#33e1ff", GREEN = "#4cc38a", GREY = "#6f7d78", MUTED = "#8b9a94", TEXT = "#e6ece9";

  function ctx(cv) {
    const dpr = window.devicePixelRatio || 1, w = cv.clientWidth, h = cv.clientHeight;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    g.fillStyle = "#101716"; g.fillRect(0, 0, w, h);
    g.font = "11px system-ui";
    return [g, w, h];
  }
  function msg(g, w, h, lines) {
    g.fillStyle = MUTED; g.textAlign = "center"; g.font = "12px system-ui";
    lines.forEach((l, i) => g.fillText(l, w / 2, h / 2 + (i - (lines.length - 1) / 2) * 16));
    g.textAlign = "left";
  }
  function title(g, a, b) {
    g.fillStyle = TEXT; g.font = "600 12px system-ui"; g.fillText(a, 10, 18);
    if (b) { g.fillStyle = MUTED; g.font = "11px system-ui"; g.fillText(b, 10, 33); }
  }
  function scaleBar(g, w, h, px, metres) {
    const L = metres * px, x = w - L - 12, y = h - 12;
    g.strokeStyle = MUTED; g.lineWidth = 1.5;
    g.beginPath(); g.moveTo(x, y - 4); g.lineTo(x, y); g.lineTo(x + L, y); g.lineTo(x + L, y - 4); g.stroke();
    g.fillStyle = MUTED; g.font = "10px system-ui"; g.fillText(`${metres} m`, x + L / 2 - 8, y - 6); g.lineWidth = 1;
  }
  function north(g, w) {
    g.fillStyle = MUTED; g.font = "700 10px system-ui"; g.fillText("N", w - 18, 18);
    g.beginPath(); g.moveTo(w - 15, 22); g.lineTo(w - 19, 32); g.lineTo(w - 11, 32); g.closePath(); g.fill();
  }

  // ------------------------------------------------------------------ measured
  function measured(cv, m) {
    if (!cv || !cv.clientWidth) return;
    const [g, w, h] = ctx(cv);
    if (!m) { msg(g, w, h, ["No audio yet.", "Each push-to-talk ends with a short chirp:", "its echoes give the distance to every wall."]); return; }
    const R = 25, cx = w / 2, cy = h / 2 + 8, px = (Math.min(w, h - 40) / 2 - 8) / R;
    title(g, "Around the phone · measured", m.echo_status);
    // distance grid
    g.strokeStyle = "rgba(255,255,255,.07)";
    for (const r of [5, 10, 15, 20, 25]) { g.beginPath(); g.arc(cx, cy, r * px, 0, 2 * Math.PI); g.stroke(); }
    g.fillStyle = "#4a5652"; g.font = "9px system-ui";
    for (const r of [5, 10, 20]) g.fillText(`${r} m`, cx + 3, cy - r * px + 10);
    // ground / ceiling band (not a wall)
    g.fillStyle = "rgba(139,154,148,.08)";
    g.beginPath(); g.arc(cx, cy, 1.8 * px, 0, 2 * Math.PI); g.arc(cx, cy, 0.8 * px, 0, 2 * Math.PI, true); g.fill();
    if (!m.probe_ok) {
      g.fillStyle = MUTED; g.textAlign = "center"; g.fillText("no echo measurement in this clip", cx, cy + R * px * 0.55); g.textAlign = "left";
    } else if (!m.echoes.length) {
      g.setLineDash([5, 4]); g.strokeStyle = GREEN; g.beginPath(); g.arc(cx, cy, R * px, 0, 2 * Math.PI); g.stroke(); g.setLineDash([]);
      g.fillStyle = GREEN; g.textAlign = "center"; g.fillText("no wall within 25 m", cx, cy + R * px - 6); g.textAlign = "left";
    }
    // echo rings: stronger echo = brighter, thicker
    m.echoes.forEach((e, i) => {
      const a = Math.max(0.35, Math.min(1, 1 + e.db / 40));
      g.strokeStyle = `rgba(51,225,255,${a})`; g.lineWidth = 1 + 2.5 * a;
      g.beginPath(); g.arc(cx, cy, e.m * px, 0, 2 * Math.PI); g.stroke();
      const ang = -Math.PI / 4 + i * 0.5;
      g.fillStyle = CYAN; g.font = "600 11px system-ui";
      g.fillText(`${e.m.toFixed(1)} m`, cx + Math.cos(ang) * e.m * px + 3, cy + Math.sin(ang) * e.m * px);
    });
    g.lineWidth = 1;
    g.fillStyle = TEXT; g.beginPath(); g.arc(cx, cy, 4, 0, 2 * Math.PI); g.fill();
    g.fillStyle = MUTED; g.font = "10px system-ui";
    g.fillText("one microphone: distance only, so each echo is a ring", 10, h - 8);
  }

  // ------------------------------------------------------------------ real place
  function place(cv, c, m) {
    if (!cv || !cv.clientWidth) return;
    const [g, w, h] = ctx(cv);
    if (!c) { msg(g, w, h, ["No candidate area yet."]); return; }
    const R = c.plan.r, cx = w / 2, cy = h / 2 + 8, px = (Math.min(w, h - 40) / 2 - 6) / R;
    const X = (x) => cx + x * px, Y = (y) => cy - y * px;
    g.save(); g.beginPath(); g.rect(0, 0, w, h); g.clip();
    // buildings, darker = taller
    for (const b of c.plan.buildings) {
      const t = Math.min(1, b.h / 25);
      g.fillStyle = `rgb(${70 - 30 * t},${84 - 30 * t},${80 - 30 * t})`;
      g.strokeStyle = "#8e9c97"; g.lineWidth = 0.8;
      g.beginPath(); b.pts.forEach(([x, y], i) => (i ? g.lineTo(X(x), Y(y)) : g.moveTo(X(x), Y(y)))); g.closePath(); g.fill(); g.stroke();
    }
    // free space seen from the spot (36 rays, 25 m)
    if (c.rays && !c.inside) {
      g.fillStyle = "rgba(232,197,71,.07)"; g.strokeStyle = "rgba(232,197,71,.35)"; g.setLineDash([2, 3]);
      g.beginPath();
      c.rays.forEach((r, k) => {
        const d = r == null ? 25 : r, a = (k * 10 * Math.PI) / 180;
        const x = X(Math.sin(a) * d), y = Y(Math.cos(a) * d);
        k ? g.lineTo(x, y) : g.moveTo(x, y);
      });
      g.closePath(); g.fill(); g.stroke(); g.setLineDash([]);
    }
    // walls that should echo: line to the foot of the perpendicular
    const heard = (m && m.echoes) || [];
    const tol = (d) => 2 * (0.5 + 0.05 * d);
    for (const e of c.expected) {
      if (e.m > 25 || e.m < 1.8) continue;
      const ok = heard.some((r) => Math.abs(r.m - e.m) < tol(e.m));
      const a = (e.bearing * Math.PI) / 180, x = X(Math.sin(a) * e.m), y = Y(Math.cos(a) * e.m);
      g.strokeStyle = ok ? GREEN : GREY; g.lineWidth = ok ? 2.2 : 1.2; g.setLineDash(ok ? [] : [4, 3]);
      g.beginPath(); g.moveTo(cx, cy); g.lineTo(x, y); g.stroke(); g.setLineDash([]);
      g.fillStyle = ok ? GREEN : GREY; g.beginPath(); g.arc(x, y, 3, 0, 2 * Math.PI); g.fill();
      g.font = "600 10px system-ui"; g.fillText(`${e.m.toFixed(1)} m`, x + 4, y - 4);
    }
    // measured rings on top
    for (const r of heard) {
      g.strokeStyle = "rgba(51,225,255,.7)"; g.lineWidth = 1.4;
      g.beginPath(); g.arc(cx, cy, r.m * px, 0, 2 * Math.PI); g.stroke();
    }
    g.restore(); g.lineWidth = 1;
    g.fillStyle = c.inside ? "#f0a33a" : TEXT; g.strokeStyle = "#0d1110"; g.lineWidth = 2;
    g.beginPath(); g.arc(cx, cy, 5, 0, 2 * Math.PI); g.fill(); g.stroke(); g.lineWidth = 1;
    title(g, `Real place · area ${c.label} · ${Math.round(c.mass * 100)}%`,
          `${c.inside ? "best spot is inside a building" : "best-fitting spot"} · fit ${c.fit != null ? Math.round(c.fit * 100) + "%" : "–"}`);
    north(g, w);
    scaleBar(g, w, h, px, 10);
    g.fillStyle = MUTED; g.font = "10px system-ui";
    g.fillText("cyan = measured echoes · green = wall that should echo, heard · grey = not heard", 10, h - 8);
  }

  return { measured, place };
})();
