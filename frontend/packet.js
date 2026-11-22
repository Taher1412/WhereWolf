// Compact packets, the same format as backend/packet.py (see there for the byte layout).
const Packet = (() => {
  const SPACES = ["indoor_small", "indoor_large", "outdoor_enclosed", "outdoor_open"];
  const SOUNDS = ["rail", "traffic", "bells", "machinery", "nature"];
  const THREATS = ["drone", "small_arms", "explosion"];
  const EVENTS = ["reached", "arrived", "lost"];
  const SIDES = [null, "left", "right", "ahead"];
  const clamp = (v, a, b) => Math.max(a, Math.min(b, Math.round(v)));
  const call = (cs) => { const b = [...(cs || "").slice(0, 8)].map((c) => c.charCodeAt(0) & 0x7f); return [b.length, ...b]; };

  function encodeReport(r, seq = 0) {
    const t = new Date();
    const out = [0x11, ...call(r.callsign)];
    const tm = ((t.getUTCHours() * 60 + t.getUTCMinutes()) << 5) | (seq & 31);
    out.push(tm >> 8, tm & 0xff);
    let mask = 0;
    const body = [];
    if (r.compass != null) { mask |= 1; body.push(clamp(((r.compass % 360) * 256) / 360, 0, 255) % 256); }
    if (r.aims && r.aims.length) {
      mask |= 2;
      const a = r.aims.slice(0, 6);
      body.push(a.length);
      a.forEach((m) => body.push(clamp((((m.az % 360) + 360) % 360) * 256 / 360, 0, 255) % 256, clamp(m.el * 4, 0, 255)));
    }
    if (r.steps != null) { mask |= 4; const s = r.steps & 0xffff; body.push(s >> 8, s & 0xff); }
    if (r.space) {
      mask |= 8;
      const q = SPACES.map((k) => clamp((r.space[k] || 0) * 15, 0, 15));
      body.push((q[0] << 4) | q[1], (q[2] << 4) | q[3]);
    }
    if (r.dba != null) { mask |= 16; body.push(clamp(r.dba, 0, 255)); }
    if (r.echoes && r.echoes.length) { mask |= 32; const e = r.echoes.slice(0, 6); body.push(e.length, ...e.map((m) => clamp(m * 4, 0, 255))); }
    if (r.sounds && Object.keys(r.sounds).length) {
      mask |= 64;
      const s = Object.entries(r.sounds).filter(([k]) => SOUNDS.includes(k)).slice(0, 5);
      body.push(s.length, ...s.map(([k, v]) => (SOUNDS.indexOf(k) << 5) | clamp(v * 31, 0, 31)));
    }
    if (r.threats && Object.keys(r.threats).length) {
      mask |= 128;
      let m = 0;
      const sc = [];
      THREATS.forEach((k, i) => { if (k in r.threats) { m |= 1 << i; sc.push(clamp(r.threats[k] * 255, 0, 255)); } });
      body.push(m, ...sc);
    }
    if (r.guide) { mask |= 256; body.push(EVENTS.indexOf(r.guide.event), (r.guide.leg || 0) & 0xff); }
    if (r.spaceStrength != null) { mask |= 512; body.push(clamp(r.spaceStrength * 255, 0, 255)); }
    out.push(mask >> 8, mask & 0xff, ...body);
    return new Uint8Array(out);
  }

  function decodeRoute(b) {
    if (!b || b[0] !== 0x21) return null;
    const n = b[1];
    const cs = String.fromCharCode(...b.slice(2, 2 + n));
    let i = 2 + n;
    const rid = b[i], k = b[i + 1];
    i += 2;
    const legs = [];
    for (let j = 0; j < k; j++) {
      const cue = (b[i + 3] << 8) | b[i + 4];
      legs.push({ bearing: (b[i] * 360) / 256, length_m: (b[i + 1] << 8) | b[i + 2], cue: cue === 0xffff ? null : cue, side: SIDES[b[i + 5]] || null });
      i += 6;
    }
    return { callsign: cs, route_id: rid, legs };
  }
  return { encodeReport, decodeRoute, SPACES, SOUNDS, THREATS };
})();
