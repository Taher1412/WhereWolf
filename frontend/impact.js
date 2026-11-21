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

  function show(d) {
    data = d;
    graph(); side();
  }

  // ---------------------------------------------------------------- graph
  function graph() {
    const host = $("impact");
    if (!data || !data.nodes.length) { host.innerHTML = `<div class="empty">No casualty details in the report yet.</div>`; return; }
    const cols = data.columns.map(() => []);
    data.nodes.forEach((n) => cols[n.col].push(n));
    const W = Math.max(host.clientWidth, 900), BOXH = 26, GAP = 8, TOP = 34;
    const colW = W / cols.length, boxW = colW - 26;
    const H = TOP + Math.max(...cols.map((c) => c.length)) * (BOXH + GAP) + 10;
    const pos = {};
    cols.forEach((c, ci) => {
      const total = c.length * (BOXH + GAP) - GAP, y0 = TOP + (H - TOP - 10 - total) / 2;
      c.forEach((n, i) => (pos[n.id] = { x: ci * colW + 13, y: y0 + i * (BOXH + GAP) }));
    });
    const fit = (t) => (t.length > Math.floor(boxW / 6.4) ? t.slice(0, Math.floor(boxW / 6.4) - 1) + "…" : t);
    let svg = `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">`;
    data.columns.forEach((c, i) => {
      svg += `<text x="${i * colW + 13}" y="16" class="ghead">${esc(c)}</text>`;
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
        <text x="${p.x + 8}" y="${p.y + 17}" font-weight="${bold}">${esc(fit(n.label))}</text></g>`;
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

  window.addEventListener("resize", () => data && graph());
  return { show };
})();
