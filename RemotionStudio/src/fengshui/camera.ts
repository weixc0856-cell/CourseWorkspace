import type {CSSProperties} from 'react';
import {clamp01, easeOut, lerp, smooth} from './theme';

export type Cam = {z: number; px: number; py: number};

type Key = [number, number, number, number]; // t, z, px, py

const KEYS: Key[] = [
  [0, 1.0, 0, 0],
  [26, 1.1, -20, -10],
  [34, 1.14, 0, 0],
  [49, 1.1, 0, 30],
  [57, 1.12, 10, 20],
  [64, 1.3, 16, -250],
  [78, 1.27, 10, -210],
  [90, 1.2, 4, -90],
  [105, 1.16, 0, -40],
  [118, 1.12, 0, -10],
  [133, 1.04, 0, 0],
  [141, 1.01, 0, 0],
  [152, 1.0, 0, 0],
];

export const camAt = (t: number): Cam => {
  if (t <= KEYS[0][0]) return {z: KEYS[0][1], px: KEYS[0][2], py: KEYS[0][3]};
  for (let i = 0; i < KEYS.length - 1; i += 1) {
    const [t0, z0, x0, y0] = KEYS[i];
    const [t1, z1, x1, y1] = KEYS[i + 1];
    if (t >= t0 && t <= t1) {
      const p = smooth((t - t0) / (t1 - t0));
      return {z: lerp(z0, z1, p), px: lerp(x0, x1, p), py: lerp(y0, y1, p)};
    }
  }
  const k = KEYS[KEYS.length - 1];
  return {z: k[1], px: k[2], py: k[3]};
};

const ANCHOR = '540px 1200px';

export const layerStyle = (cam: Cam, depth: number): CSSProperties => {
  const z = 1 + (cam.z - 1) * depth;
  return {
    position: 'absolute',
    inset: 0,
    transformOrigin: ANCHOR,
    transform: `translate(${(cam.px * depth).toFixed(2)}px, ${(cam.py * depth).toFixed(2)}px) scale(${z.toFixed(4)})`,
    willChange: 'transform',
  };
};

export const toScreen = (cam: Cam, depth: number, x: number, y: number): [number, number] => {
  const z = 1 + (cam.z - 1) * depth;
  return [540 + (x - 540) * z + cam.px * depth, 1200 + (y - 1200) * z + cam.py * depth];
};

// the ridge silhouette the whole film is built on
export const HORIZON = 1520;
const gauss = (x: number, cx: number, w: number) => Math.exp(-(((x - cx) / w) ** 2));
const wobble = (x: number, seed: number) =>
  Math.sin(x * 0.031 + seed) * 2.4 + Math.sin(x * 0.087 + seed * 2.3) * 1.1;

export const ridgeTop = (x: number) =>
  HORIZON - 470 * gauss(x, 566, 268) - 26 * gauss(x, 426, 147) + wobble(x, 1.7);

// steady wind field drawn for the paper ridge: climbs the windward slope,
// accelerates over the crest, stalls and settles in the lee
export const windAt = (x: number, y: number): [number, number] => {
  const r = ridgeTop(x);
  const d = Math.max(0, r - y);
  const near = Math.exp(-((d / 240) ** 2));
  const crest = Math.exp(-(((x - 566) / 300) ** 2));
  const slope = (ridgeTop(x + 3) - ridgeTop(x - 3)) / 6;
  const lee = smooth(clamp01((x - 640) / 220)) * Math.exp(-((d / 280) ** 2));
  const pocket = Math.exp(-(((x - 790) / 150) ** 2)) * Math.exp(-((d / 130) ** 2));
  const u = 1 + 1.05 * crest * near - 0.85 * lee - 0.35 * pocket;
  const v = slope * u * near * 0.9 + 0.55 * lee + 0.5 * pocket * Math.sin(d / 60);
  return [u, v];
};

export const speedAt = (x: number, y: number) => {
  const [u, v] = windAt(x, y);
  return Math.hypot(u, v);
};

export type Path = {pts: [number, number][]; speed: number[]};

const STEP = 4;

export const buildPaths = (seeds: number[]): Path[] => {
  const out: Path[] = [];
  for (const y0 of seeds) {
    const pts: [number, number][] = [];
    const sp: number[] = [];
    let x = -60;
    let y = y0;
    for (let i = 0; i < 700; i += 1) {
      const [u, v] = windAt(x, y);
      const m = Math.hypot(u, v) || 1;
      pts.push([x, y]);
      sp.push(m);
      const nx = x + (u / m) * STEP;
      const ny = y + (v / m) * STEP;
      const [u2, v2] = windAt(nx, ny);
      const m2 = Math.hypot(u2, v2) || 1;
      x += ((u / m + u2 / m2) / 2) * STEP;
      y += ((v / m + v2 / m2) / 2) * STEP;
      if (x > 1180 || y > HORIZON - 4 || y < 120) break;
      if (y > ridgeTop(x) - 6) break;
    }
    if (pts.length > 40) out.push({pts, speed: sp});
  }
  return out;
};

export const samplePath = (p: Path, s: number): [number, number] => {
  const i = Math.max(0, Math.min(p.pts.length - 1, s / STEP));
  const i0 = Math.floor(i);
  const f = i - i0;
  const a = p.pts[i0];
  const b = p.pts[Math.min(p.pts.length - 1, i0 + 1)];
  return [lerp(a[0], b[0], f), lerp(a[1], b[1], f)];
};

export const ease = easeOut;
