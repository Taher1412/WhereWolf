// Casualty digital twin (step 4 of the pipeline page): a 3D body posed and marked
// from the voice report (backend/body.py). Three.js, loaded as an ES module.
//
// Colours = what was SAID, never an assessment:
//   red bleeding (pulsing when massive bleeding was reported), orange burn,
//   purple fracture, pink gunshot, coral shrapnel, dark red amputation, yellow other.
//   Paler = side not said (both sides are marked). Orange band = tourniquet.
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const KIND_COLOR = { bleeding: 0xe5484d, burn: 0xf0a33a, fracture: 0xb07cff, gunshot: 0xff3b8b,
                     shrapnel: 0xff7a45, amputation: 0x8b0000, injury: 0xf5d76e };
const BASE = new THREE.Color(0x7d8b96);
const SEG_NAME = { head: "head", neck: "neck", chest: "chest", abdomen: "abdomen", pelvis: "pelvis",
  l_upper_arm: "L upper arm", l_forearm: "L forearm", l_hand: "L hand", r_upper_arm: "R upper arm",
  r_forearm: "R forearm", r_hand: "R hand", l_thigh: "L thigh", l_lower_leg: "L lower leg", l_foot: "L foot",
  r_thigh: "R thigh", r_lower_leg: "R lower leg", r_foot: "R foot" };

// ------------------------------------------------------------------ scene
const canvas = $("body"), box = $("bodyView"), labels = $("bodyLabels");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio || 1);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, 1, 0.05, 50);
const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true; controls.autoRotate = true; controls.autoRotateSpeed = 1.2;
canvas.addEventListener("pointerdown", () => (controls.autoRotate = false));
canvas.addEventListener("dblclick", () => { controls.autoRotate = true; frame(); });
scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x1b2320, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(2, 4, 3); scene.add(sun);
const ground = new THREE.Mesh(new THREE.CircleGeometry(1.6, 64), new THREE.MeshStandardMaterial({ color: 0x18201d, roughness: 1 }));
ground.rotation.x = -Math.PI / 2; scene.add(ground);
const grid = new THREE.GridHelper(3.2, 16, 0x2a3531, 0x222b28); grid.position.y = 0.001; scene.add(grid);

let meshCache = {}, body = null, mdata = null, twin = null, pick = 0, extras = [], anchors = [], pulse = [];

function resize() {
  const w = box.clientWidth, h = box.clientHeight;
  renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(box);

async function getMesh(posture) {
  if (!meshCache[posture]) {
    const r = await fetch(`/api/body_mesh/${posture}`);
    meshCache[posture] = r.ok ? await r.json() : null;
  }
  return meshCache[posture];
}

function frame() {
  if (!body) return;
  const bb = new THREE.Box3().setFromObject(body), c = bb.getCenter(new THREE.Vector3()), s = bb.getSize(new THREE.Vector3());
  const r = Math.max(s.x, s.y, s.z);
  controls.target.copy(c);
  camera.position.set(c.x + r * 0.75, c.y + r * 0.6, c.z + r * 0.95);
  controls.update();
}

// ------------------------------------------------------------------ build
async function build() {
  const cas = twin && twin.casualties[pick];
  const m = await getMesh(twin ? twin.posture : "supine");
  if (!m) { $("bodyNote").textContent = "Body mesh missing: run  python -m scripts.build_body"; return; }
  $("bodyNote").textContent = "";
  if (!body || mdata !== m) {
    if (body) { scene.remove(body); body.geometry.dispose(); }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(m.verts, 3));
    g.setIndex(m.faces);
    g.computeVertexNormals();
    g.setAttribute("color", new THREE.Float32BufferAttribute(new Float32Array(m.verts.length), 3));
    body = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.75, metalness: 0.05 }));
    scene.add(body);
    mdata = m;
    frame();
  }
  paint(cas);
}

function segVerts(segName, surface) {
  const s = mdata.segments.indexOf(segName), out = [];
  for (let i = 0; i < mdata.seg.length; i++) {
    if (mdata.seg[i] !== s) continue;
    if (surface === "back" && mdata.front[i]) continue;
    if (surface === "front" && !mdata.front[i]) continue;
    out.push(i);
  }
  return out;
}

function paint(cas) {
  const col = body.geometry.getAttribute("color");
  for (let i = 0; i < col.count; i++) col.setXYZ(i, BASE.r, BASE.g, BASE.b);
  extras.forEach((o) => scene.remove(o)); extras = []; anchors = []; pulse = [];
  labels.innerHTML = "";
  if (!cas) { col.needsUpdate = true; return; }
  const P = body.geometry.getAttribute("position");

  for (const inj of cas.injuries) {
    const c = new THREE.Color(KIND_COLOR[inj.kind] || KIND_COLOR.injury);
    const pale = inj.side === null && inj.segments.some((s) => s.startsWith("l_") || s.startsWith("r_"));
    if (pale) c.lerp(BASE, 0.45);
    for (const s of inj.segments) {
      // Trunk wounds: front surface unless "back" was said.
      const surf = inj.surface || (["chest", "abdomen", "pelvis"].includes(s) ? "front" : null);
      const idx = segVerts(s, surf);
      idx.forEach((i) => col.setXYZ(i, c.r, c.g, c.b));
      if (inj.massive) pulse.push({ idx, c });
      if (idx.length) {
        const ctr = new THREE.Vector3();
        idx.forEach((i) => ctr.add(new THREE.Vector3(P.getX(i), P.getY(i), P.getZ(i))));
        ctr.divideScalar(idx.length);
        anchors.push({ p: ctr, html: `${SEG_NAME[s]} · ${inj.kind}${inj.massive ? " (massive)" : ""}${pale ? " · side?" : ""}`,
                       color: "#" + c.getHexString() });
      }
    }
  }
  col.needsUpdate = true;

  // Tourniquet bands: high on the limb, between its two joints.
  for (const tq of cas.tourniquets) {
    const J = mdata.joint_xyz, a = new THREE.Vector3(...J[mdata.joints[tq.from]]), b = new THREE.Vector3(...J[mdata.joints[tq.to]]);
    const axis = b.clone().sub(a), len = axis.length(); axis.normalize();
    const p = a.clone().addScaledVector(axis, len * tq.at);
    let r = 0.04;
    for (const i of segVerts(tq.segment)) {
      const v = new THREE.Vector3(P.getX(i), P.getY(i), P.getZ(i)).sub(p);
      const along = v.dot(axis);
      if (Math.abs(along) < 0.025) r = Math.max(r, v.addScaledVector(axis, -along).length());
    }
    const ring = new THREE.Mesh(new THREE.TorusGeometry(r * 1.08, 0.02, 12, 48),
                                new THREE.MeshStandardMaterial({ color: 0xf0a33a, emissive: 0x6a3a00, roughness: 0.5 }));
    ring.position.copy(p);
    ring.quaternion.setFromUnitVectors(new THREE.Vector3(0, 0, 1), axis);
    scene.add(ring); extras.push(ring);
    anchors.push({ p: p.clone(), tq, color: "#f0a33a" });
  }
  labels.innerHTML = anchors.map((a, i) => `<div class="blabel${a.tq ? " tq" : ""}" id="bl${i}" style="border-color:${a.color};color:${a.color}"></div>`).join("");
}

// ------------------------------------------------------------------ side panel
function fmtMin(ms) { const m = Math.floor(ms / 60000); return `${m} min`; }
function tqText(tq) {
  if (!tq.tq_ms) return `TQ ${tq.time || "time?"}`;
  return `TQ ${tq.time} · ${fmtMin(Date.now() - tq.tq_ms)}`;
}

function panel() {
  if (!twin || !twin.casualties.length) {
    $("bodyTabs").innerHTML = ""; $("bodyBadges").innerHTML = "";
    $("bodyList").innerHTML = `<li>No casualty details in the report yet.</li>`;
    return;
  }
  $("bodyTabs").innerHTML = twin.casualties.length > 1 ? twin.casualties.map((c, i) =>
    `<button data-i="${i}" class="${i === pick ? "on" : ""}">#${i + 1}${c.count > 1 ? ` ×${c.count}` : ""}</button>`).join("") : "";
  $("bodyTabs").querySelectorAll("button").forEach((b) => (b.onclick = () => { pick = Number(b.dataset.i); panel(); build(); }));
  const c = twin.casualties[pick], s = c.signs || {};
  const badge = (txt, cls) => `<span class="badge ${cls}">${esc(txt)}</span>`;
  const sign = (v, yes, no) => (v === true ? badge(yes, "ok") : v === false ? badge(no, "bad") : badge(yes.split(" ")[0] + " ?", ""));
  $("bodyBadges").innerHTML = [
    badge(c.priority, { urgent: "bad", priority: "warn", routine: "ok" }[c.priority]),
    sign(s.conscious, "conscious", "unconscious"), sign(s.breathing, "breathing", "breathing problem"),
    s.massive_bleeding ? badge("massive bleeding", "bad") : "",
    badge(twin.posture_label + (twin.posture_said ? "" : " (assumed)"), twin.posture_said ? "" : "dim"),
    c.mobility ? badge(c.mobility.label + (c.mobility.source === "said" ? "" : " (inferred)") + (c.mobility.conflict ? " ⚠" : ""),
                       { walks: "ok", assisted: "warn", litter: "bad", trapped: "bad", unknown: "dim" }[c.mobility.state]) : "",
    ...c.tourniquets.map((t) => `<span class="badge warn" data-tqms="${t.tq_ms || ""}" data-time="${t.time || ""}">${esc(tqText(t))}</span>`),
  ].join("");
  const items = [];
  if (c.mechanism) items.push(`<li><span class="tag">said</span><b>mechanism</b> ${esc(c.mechanism)}</li>`);
  for (const inj of c.injuries) items.push(`<li><span class="tag">said</span><b>“${esc(inj.text)}”</b> → ${esc(inj.segments.map((x) => SEG_NAME[x]).join(", "))}${inj.surface ? " (back)" : ""} · ${inj.kind}${inj.side === null && inj.segments.some((x) => x[1] === "_") ? " · side not said" : ""}</li>`);
  for (const t of c.tourniquets) items.push(`<li><span class="tag">said</span><b>tourniquet</b> ${esc(t.said || "location not said")} → ${SEG_NAME[t.segment]}${t.side_said ? "" : " (side inferred from the wound)"}, ${esc(t.time || "time not said")}</li>`);
  for (const u of c.unmapped) items.push(`<li><span class="tag">said</span>“${esc(u)}” (no body part recognised)</li>`);
  for (const t of c.treatments) items.push(`<li><span class="tag">said</span><b>treatment</b> ${esc(t)}</li>`);
  for (const q of twin.sound_cues) items.push(`<li><span class="tag">audio</span><b>${esc(q.label)}</b> ${q.score} · ${esc(q.note)}</li>`);
  if (c.mobility) items.push(`<li><span class="tag">${c.mobility.source}</span><b>mobility</b> ${esc(c.mobility.label)}: ${esc(c.mobility.evidence.join("; "))}${c.mobility.conflict ? ` · <span style="color:var(--warn)">⚠ ${esc(c.mobility.conflict)}: stretcher planned</span>` : ""}</li>`);
  if (!twin.posture_said) items.push(`<li><span class="tag">assumed</span>posture not said: drawn lying on the back</li>`);
  $("bodyList").innerHTML = items.join("");
}

// ------------------------------------------------------------------ loop
const tmp = new THREE.Vector3();
renderer.setAnimationLoop((t) => {
  controls.update();
  if (body && pulse.length) {
    const col = body.geometry.getAttribute("color"), k = 0.55 + 0.45 * Math.sin(t / 180);
    for (const p of pulse) { const c = p.c.clone().multiplyScalar(0.45 + 0.75 * k); p.idx.forEach((i) => col.setXYZ(i, c.r, c.g, c.b)); }
    col.needsUpdate = true;
  }
  renderer.render(scene, camera);
  const w = box.clientWidth, h = box.clientHeight;
  anchors.forEach((a, i) => {
    const el = document.getElementById("bl" + i);
    if (!el) return;
    tmp.copy(a.p).project(camera);
    el.style.left = `${(tmp.x * 0.5 + 0.5) * w}px`; el.style.top = `${(-tmp.y * 0.5 + 0.5) * h}px`;
    el.textContent = a.tq ? tqText(a.tq) : a.html;
  });
});
setInterval(() => document.querySelectorAll("#bodyBadges [data-tqms]").forEach((el) => {
  if (el.dataset.tqms) el.textContent = `TQ ${el.dataset.time} · ${fmtMin(Date.now() - Number(el.dataset.tqms))}`;
}), 15000);

// ------------------------------------------------------------------ entry
window.Body3D = {
  show(t) {
    if (!t) return;
    if (!twin || twin.report_id !== t.report_id) { pick = 0; controls.autoRotate = true; }
    twin = t;
    if (pick >= twin.casualties.length) pick = 0;
    panel(); build();
  },
};
if (window.__pendingTwin) window.Body3D.show(window.__pendingTwin);
build();
