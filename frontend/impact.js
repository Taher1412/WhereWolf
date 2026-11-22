// Steps 5 and 6 of the pipeline page (backend/response.py):
//   5  Impact graph: Reported -> Body region -> Possibly impacted (check) -> MARCH threat -> Bring
//   6  Bring & send: kit list in MARCH order, and how many people to send.
// Plain SVG, layered left to right. Hover a node to follow its chain.

const Impact = (() => {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const STATUS = {
    critical: { stroke: "#e5484d", fill: "rgba(229,72,77,.16)" },
    severe: { stroke: "#f0a33a", fill: "rgba(240,163,58,.14)" },
    mild: { stroke: "#e8c547", fill: "rgba(232,197,71,.10)" },
    possible: { stroke: "#e8c547", fill: "rgba(232,197,71,.04)", dash: "4 3" },
    info: { stroke: "#4cc38a", fill: "rgba(76,195,138,.10)" },
  };
  const EDGE = { reported: ["#c9d3cf", ""], possible: ["#e8c547", "4 3"], threatens: ["#e5484d", ""], needs: ["#4cc38a", ""] };
  let data = null;
  // Dashboard only (#graphMode): switch between the impact graph and the body parts graph.
  let mode = localStorage.getItem("pothenot_graph") === "body" ? "body" : "impact";
  let body = null, bpick = 0;

  function show(d) {
    data = d;
    render(); side();
  }
  function showBody(t) {
    if (!t || !body || body.report_id !== t.report_id) bpick = 0;
    body = t;
    if (mode === "body") render();
  }
  function render() {
    const sw = $("graphMode");
    if (sw && mode === "body") bodyGraph(); else graph();
    if (!sw) return;
    sw.querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.m === mode));
    $("graphTitle").textContent = mode === "body" ? "Body parts" : "Impact graph";
    $("graphMeta").textContent = mode === "body"
      ? "every body part · red = affected · orange = no data"
      : "reported → body region → possibly impacted → threat → bring · hover a box to follow its chain";
    $("legendImpact").hidden = mode === "body";
    $("legendBody").hidden = mode !== "body";
  }
  function setMode(m) {
    mode = m;
    localStorage.setItem("pothenot_graph", m);
    render();
  }
  function wire() {
    const sw = $("graphMode");
    if (sw) sw.querySelectorAll("button").forEach((b) => (b.onclick = () => setMode(b.dataset.m)));
    if (sw) render();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire); else wire();

  // ---------------------------------------------------------------- body parts graph
  // Body -> 7 regions -> parts (backend/bodygraph.py). One column per region, parts hang
  // under their region like a tree. Red = affected (said), orange = nothing said yet.
  const BST = { affected: { stroke: "#e5484d", fill: "rgba(229,72,77,.38)" },
                nodata: { stroke: "#f0a33a", fill: "rgba(240,163,58,.16)" } };
  function bodyGraph() {
    const host = $("impact");
    const cs = (body && body.casualties) || [];
    if (!cs.length) { host.innerHTML = `<div class="empty">No casualty in the report yet.</div>`; return; }
    if (bpick >= cs.length) bpick = 0;
    const nodes = cs[bpick].parts || [];
    const regions = nodes.filter((n) => n.parent === "body");
    const kids = (id) => nodes.filter((n) => n.parent === id);
    const maxK = Math.max(...regions.map((r) => kids(r.id).length));
    const pick = cs.length > 1 ? `<div class="bpick">${cs.map((c, i) =>
      `<button class="${i === bpick ? "on" : ""}" data-i="${i}">Casualty ${i + 1}${c.count > 1 ? ` ×${c.count}` : ""}</button>`).join("")}</div>` : "";
    const fit0 = host.dataset.fit && host.clientHeight > 0;
    const rows = maxK + 2.4;
    const availH = (fit0 ? host.clientHeight : 420) - (cs.length > 1 ? 26 : 0) - 12;
    const pitch = Math.max(16, Math.min(34, availH / rows));          // box + gap, fits the tile
    const BOXH = pitch * 0.8, GAP = pitch * 0.2;
    const W = Math.max(host.clientWidth - 6, 560), colW = W / regions.length, boxW = colW - 16, indent = 12;
    const FS = BOXH < 16 ? 9.5 : BOXH < 20 ? 10.5 : 12;
    const yRoot = 4, yReg = yRoot + (BOXH + GAP) * 1.4;
    const H = yReg + (maxK + 1) * (BOXH + GAP) + 6;
    const pos = { body: { x: W / 2 - boxW / 2, y: yRoot, w: boxW } };
    regions.forEach((r, i) => {
      pos[r.id] = { x: i * colW + 8, y: yReg, w: boxW };
      kids(r.id).forEach((k, j) => (pos[k.id] = { x: i * colW + 8 + indent, y: yReg + (j + 1) * (BOXH + GAP), w: boxW - indent }));
    });
    const cw = FS * 0.55, fit = (t, w) => (t.length > Math.floor((w - 12) / cw) ? t.slice(0, Math.floor((w - 12) / cw) - 1) + "…" : t);
    let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="font-size:${FS}px">`;
    const line = (d, n) => `<path d="${d}" fill="none" stroke="${n.status === "affected" ? "#e5484d" : "#f0a33a"}" stroke-width="1.2" opacity="${n.status === "affected" ? 0.8 : 0.35}"/>`;
    const r0 = pos.body;
    for (const r of regions) {
      const p = pos[r.id], x1 = r0.x + r0.w / 2, y1 = r0.y + BOXH, x2 = p.x + p.w / 2, y2 = p.y, my = (y1 + y2) / 2;
      svg += line(`M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`, r);
      for (const k of kids(r.id)) {
        const q = pos[k.id], xs = p.x + indent / 2, ym = q.y + BOXH / 2;
        svg += line(`M${xs},${p.y + BOXH} L${xs},${ym} L${q.x},${ym}`, k);
      }
    }
    for (const n of nodes) {
      const p = pos[n.id];
      if (!p) continue;
      const st = BST[n.status] || BST.nodata;
      const tip = n.said.length ? n.said.join("\n") : (n.status === "affected" ? "affected: see the parts below" : "no data: nothing said about it yet");
      const weight = n.parent === "body" || n.id === "body" ? 700 : n.direct ? 650 : 500;
      svg += `<g class="gnode"><title>${esc(n.label)}\n${esc(tip)}</title>
        <rect x="${p.x}" y="${p.y}" width="${p.w}" height="${BOXH}" rx="6" fill="${st.fill}" stroke="${st.stroke}" stroke-width="${n.direct ? 1.8 : 1.1}"/>
        <text x="${p.x + 7}" y="${p.y + BOXH / 2 + FS * 0.36}" font-weight="${weight}">${esc(fit(n.label, p.w))}</text></g>`;
    }
    svg += `</svg>`;
    host.innerHTML = pick + svg;
    host.querySelectorAll(".bpick button").forEach((b) => (b.onclick = () => { bpick = Number(b.dataset.i); bodyGraph(); }));
  }

  // ---------------------------------------------------------------- graph
  function graph() {
    const host = $("impact");
    if (!data || !data.nodes.length) { host.innerHTML = `<div class="empty">No casualty details in the report yet.</div>`; return; }
    const cols = data.columns.map(() => []);
    data.nodes.forEach((n) => cols[n.col].push(n));
    // data-fit (dashboard tile): shrink the boxes to fit the tile height, down to a readable minimum.
    const fit0 = host.dataset.fit && host.clientHeight > 0;
    const maxN = Math.max(...cols.map((c) => c.length));
    const BOXH = fit0 ? Math.max(13, Math.min(32, (host.clientHeight - 24 - 6) / maxN - 5)) : 26;
    const GAP = fit0 ? Math.max(3, Math.min(8, BOXH * 0.3)) : 8, TOP = fit0 ? 22 : 34;
    const W = fit0 ? Math.max(host.clientWidth - 4, 560) : Math.max(host.clientWidth, 900);
    const FS = BOXH < 16 ? 9.5 : BOXH < 20 ? 10.5 : BOXH > 28 ? 13 : 12;
    const colW = W / cols.length, boxW = colW - 26;
    const H = TOP + Math.max(...cols.map((c) => c.length)) * (BOXH + GAP) + 10;
    const pos = {};
    cols.forEach((c, ci) => {
      const total = c.length * (BOXH + GAP) - GAP, y0 = TOP + (H - TOP - 10 - total) / 2;
      c.forEach((n, i) => (pos[n.id] = { x: ci * colW + 13, y: y0 + i * (BOXH + GAP) }));
    });
    const cw = FS * 0.53, fit = (t) => (t.length > Math.floor(boxW / cw) ? t.slice(0, Math.floor(boxW / cw) - 1) + "…" : t);
    let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="font-size:${FS}px">`;
    data.columns.forEach((c, i) => {
      svg += `<text x="${i * colW + 13}" y="${TOP - 10}" class="ghead">${esc(c)}</text>`;
    });
    for (const e of data.edges) {
      const a = pos[e.from], b = pos[e.to];
      if (!a || !b) continue;
      const x1 = a.x + boxW, y1 = a.y + BOXH / 2, x2 = b.x, y2 = b.y + BOXH / 2, mx = (x1 + x2) / 2;
      const [col, dash] = EDGE[e.type] || EDGE.reported;
      svg += `<path class="gedge" data-a="${esc(e.from)}" data-b="${esc(e.to)}" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}"
        stroke="${col}" stroke-dasharray="${dash}" fill="none" stroke-width="1.3" opacity=".55"/>`;
    }
    for (const n of data.nodes) {
      const p = pos[n.id], st = STATUS[n.status] || STATUS.info, bold = n.group === "march" ? "700" : "500";
      svg += `<g class="gnode" data-id="${esc(n.id)}"><title>${esc(n.label)}${n.detail ? " · " + esc(n.detail) : ""}</title>
        <rect x="${p.x}" y="${p.y}" width="${boxW}" height="${BOXH}" rx="6" fill="${st.fill}" stroke="${st.stroke}" stroke-dasharray="${st.dash || ""}"/>
        <text x="${p.x + 8}" y="${p.y + BOXH / 2 + FS * 0.36}" font-weight="${bold}">${esc(fit(n.label))}</text></g>`;
    }
    svg += `</svg>`;
    host.innerHTML = svg;
    hover(host);
  }

  // Hover: highlight everything upstream and downstream of a node.
  function hover(host) {
    const out = {}, inn = {};
    data.edges.forEach((e) => { (out[e.from] = out[e.from] || []).push(e.to); (inn[e.to] = inn[e.to] || []).push(e.from); });
    const walk = (id, adj, seen) => { (adj[id] || []).forEach((n) => { if (!seen.has(n)) { seen.add(n); walk(n, adj, seen); } }); return seen; };
    host.querySelectorAll(".gnode").forEach((g) => {
      g.onmouseenter = () => {
        const id = g.dataset.id, keep = new Set([id, ...walk(id, out, new Set()), ...walk(id, inn, new Set())]);
        host.querySelectorAll(".gnode").forEach((x) => (x.style.opacity = keep.has(x.dataset.id) ? 1 : 0.18));
        host.querySelectorAll(".gedge").forEach((x) => (x.style.opacity = keep.has(x.dataset.a) && keep.has(x.dataset.b) ? 0.95 : 0.05));
      };
      g.onmouseleave = () => {
        host.querySelectorAll(".gnode").forEach((x) => (x.style.opacity = 1));
        host.querySelectorAll(".gedge").forEach((x) => (x.style.opacity = 0.55));
      };
    });
  }

  // ---------------------------------------------------------------- bring & send
  function side() {
    const host = $("bring");
    if (!data || !data.casualties) { host.innerHTML = `<div class="empty">Waiting for casualty details.</div>`; return; }
    const t = data.team;
    const groups = {};
    data.kit.forEach((k) => (groups[k.march || "·"] = groups[k.march || "·"] || []).push(k));
    const MARCH = { M: "Massive bleeding", A: "Airway", R: "Respiration", C: "Circulation", H: "Hypothermia / Head", "·": "General" };
    const kit = Object.entries(groups).map(([m, ks]) => `<div class="kgroup"><div class="kletter">${m}</div><div>
        <div class="kname">${MARCH[m]}</div>
        ${ks.map((k) => `<div class="kitem"><b>${k.qty}×</b> ${esc(k.name)} <span class="who ${k.who}">${k.who}</span>
          <div class="kwhy">${esc(k.why)}</div></div>`).join("")}</div></div>`).join("");
    const MOB = { walks: "can walk", assisted: "needs help", litter: "stretcher", trapped: "trapped", unknown: "mobility unknown" };
    const rows = t.rows.map((r) => `<li>Casualty ${r.casualty}${r.count > 1 ? ` ×${r.count}` : ""} · <b>${esc(r.priority)}</b> ·
      <span class="mob ${r.mobility}">${MOB[r.mobility]}</span> ${esc(r.carry)}
      <span class="muted">(${esc(r.source)}: ${esc(r.why)})</span></li>`).join("");
    host.innerHTML = `
      <div class="send"><div class="big">${t.total}</div><div>
        <div class="slabel">people to send</div>
        <div class="muted">${t.bearers} bearer${t.bearers === 1 ? "" : "s"} · ${t.medics} medic${t.medics === 1 ? "" : "s"} · ${t.escorts} escort${t.escorts === 1 ? "" : "s"}${t.extrication ? ` · ${t.extrication} extraction` : ""}${t.distance_m != null ? ` · ${t.distance_m} m to the collection point` : ""}</div></div></div>
      <ul class="tlines">${t.lines.map((l) => `<li>${esc(l)}</li>`).join("")}${rows}</ul>
      ${t.notes.map((n) => `<div class="tnote">${esc(n)}</div>`).join("")}
      <div class="clabel" style="margin-top:10px">Bring (MARCH order)</div>
      <div class="kit">${kit}</div>
      <div class="hint">${esc(data.disclaimer)}</div>`;
  }

  window.addEventListener("resize", () => (data || body) && render());
  return { show, showBody, render };
})();
