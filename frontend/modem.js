// Data over a voice radio, the same modem as backend/modem.py (tones 1200 / 2200 Hz, 400 bit/s,
// preamble 0x55 x6, then twice: sync 0x2D 0xD4 | length | payload | CRC-16).
// encode() -> Float32Array to play into the radio's mic; decode() -> payloads heard on the mic.
const Modem = (() => {
  const BAUD = 400, F1 = 1200, F0 = 2200;
  const PRE = [0x55, 0x55, 0x55, 0x55, 0x55, 0x55], SYNC = [0x2d, 0xd4];

  function crc16(bytes) {
    let c = 0xffff;
    for (const b of bytes) {
      c ^= b << 8;
      for (let i = 0; i < 8; i++) c = (c & 0x8000 ? (c << 1) ^ 0x1021 : c << 1) & 0xffff;
    }
    return c;
  }
  const bitsOf = (bytes) => bytes.flatMap((b) => [7, 6, 5, 4, 3, 2, 1, 0].map((i) => (b >> i) & 1));

  function encode(payload, sr = 48000, copies = 2, amp = 0.6) {
    const p = Array.from(payload), c = crc16(p);
    const body = [...SYNC, p.length, ...p, c >> 8, c & 0xff];
    let frame = [...PRE];
    for (let k = 0; k < copies; k++) frame = frame.concat(body);
    const bits = bitsOf(frame), spb = sr / BAUD, n = Math.round(bits.length * spb), pad = Math.round(0.05 * sr);
    const out = new Float32Array(n + 2 * pad), ramp = Math.round(0.005 * sr);
    let ph = 0;
    for (let i = 0; i < n; i++) {
      const b = bits[Math.min(bits.length - 1, Math.floor(i / spb))];
      ph += (2 * Math.PI * (b ? F1 : F0)) / sr;
      let a = amp * Math.sin(ph);
      if (i < ramp) a *= i / ramp;
      if (i > n - ramp) a *= (n - i) / ramp;
      out[pad + i] = a;
    }
    return out;
  }

  // |sum over one bit| of x * e^(-j 2 pi f t), for a window starting at each sample
  function toneEnergy(x, f, sr, k) {
    const n = x.length, re = new Float64Array(n + 1), im = new Float64Array(n + 1);
    for (let i = 0; i < n; i++) {
      const a = (2 * Math.PI * f * i) / sr;
      re[i + 1] = re[i] + x[i] * Math.cos(a);
      im[i + 1] = im[i] - x[i] * Math.sin(a);
    }
    const e = new Float64Array(Math.max(0, n - k + 1));
    for (let i = 0; i < e.length; i++) e[i] = Math.hypot(re[i + k] - re[i], im[i + k] - im[i]);
    return e;
  }

  function decode(x, sr = 48000) {
    const spb = sr / BAUD, k = Math.round(spb);
    if (x.length < spb * 8 * 11) return [];
    const e1 = toneEnergy(x, F1, sr, k), e0 = toneEnergy(x, F0, sr, k);
    const d = new Float64Array(e1.length);
    for (let i = 0; i < d.length; i++) d[i] = e1[i] - e0[i];
    const syncBits = bitsOf(SYNC), found = [], seen = new Set();
    const byteAt = (soft, p) => { let v = 0; for (let j = 0; j < 8; j++) v = (v << 1) | (soft[p + j] > 0 ? 1 : 0); return v; };
    for (let ph = 0; ph < spb; ph += spb / 8) {
      const soft = [];
      for (let t = ph; t < d.length; t += spb) soft.push(d[Math.floor(t)]);
      const hits = [];
      for (let h = 0; h + 16 <= soft.length; h++) {
        let ok = 0;
        for (let j = 0; j < 16; j++) if ((soft[h + j] > 0 ? 1 : 0) === syncBits[j]) ok++;
        if (ok >= 15) hits.push(h);
      }
      for (const h of hits) {
        const p = h + 16, lens = new Set();
        if (p + 8 <= soft.length) lens.add(byteAt(soft, p));
        for (const h2 of hits) { const gap = h2 - h - 24; if (gap > 16 && gap % 8 === 0) lens.add(gap / 8 - 2); }
        for (const ln of lens) {
          const n = 8 + 8 * (ln + 2), span = 16 + n;
          for (const q of [null, p + span, p - span]) {
            if (p + n > soft.length || (q !== null && (q < 0 || q + n > soft.length))) continue;
            const s2 = soft.slice();
            if (q !== null) for (let j = 0; j < n; j++) s2[p + j] = soft[p + j] + soft[q + j];
            const body = [];
            for (let j = 0; j < ln + 2; j++) body.push(byteAt(s2, p + 8 + 8 * j));
            const pay = body.slice(0, ln), c = (body[ln] << 8) | body[ln + 1];
            const key = pay.join(",");
            if (crc16(pay) === c && !seen.has(key)) { seen.add(key); found.push(new Uint8Array(pay)); }
          }
        }
      }
      if (found.length) break;
    }
    return found;
  }

  // Play tones on the phone speaker (hold it against the radio's mic, PTT pressed).
  async function play(payload) {
    const ctx = new AudioContext(), x = encode(payload, ctx.sampleRate);
    const b = ctx.createBuffer(1, x.length, ctx.sampleRate);
    b.copyToChannel(x, 0);
    const s = ctx.createBufferSource();
    s.buffer = b;
    s.connect(ctx.destination);
    s.start();
    await new Promise((r) => (s.onended = r));
    ctx.close();
    return x.length / ctx.sampleRate;
  }
  return { encode, decode, play, crc16 };
})();
