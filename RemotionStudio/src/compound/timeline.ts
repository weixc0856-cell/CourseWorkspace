export const FPS = 30;
export const DURATION = 152;
export const W = 1080;
export const H = 1920;

export const BPM = 128;
export const BEAT_OFFSET = 0;
export const BEAT_S = 60 / BPM;
export const BAR_S = BEAT_S * 4;

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
export const smooth = (v: number) => {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
};
export const easeOut = (v: number) => 1 - Math.pow(1 - clamp01(v), 3);
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;

export const beatPhase = (t: number) => {
  const v = ((t - BEAT_OFFSET) / BEAT_S) % 1;
  return ((v % 1) + 1) % 1;
};
export const beatPulse = (t: number, decay = 7) => Math.exp(-beatPhase(t) * decay);
export const barPhase = (t: number) => {
  const v = ((t - BEAT_OFFSET) / BAR_S) % 1;
  return ((v % 1) + 1) % 1;
};

export const STAGE_TIMES = [0, 11.25, 16.875, 22.5, 28.125, 33.75, 39.375];
export const STAGES = STAGE_TIMES.length - 1;
export const REVEAL = 60;
export const REMOVE = 78.75;
export const RESTORE = 103.125;
export const FINAL = 130.3125;
export const END = 150;

export const DIMS: Array<[number, number, number]> = [
  [1, 1, 1],
  [2, 1, 1],
  [2, 1, 2],
  [2, 2, 2],
  [4, 2, 2],
  [4, 2, 4],
  [4, 4, 4],
];

export const SPACING = 1.08;
export const CUBE = 0.9;
export const MAX_CUBES = 64;

export function stageAt(t: number) {
  let k = 0;
  for (let i = 1; i < STAGE_TIMES.length; i += 1) {
    if (t >= STAGE_TIMES[i]) k = i;
  }
  const t0 = STAGE_TIMES[k];
  const isTransition = k > 0 && t < STAGE_TIMES[k] + 1.7;
  const p = isTransition ? smooth((t - t0) / 1.7) : 1;
  return {k, p, isTransition, t0};
}

export function posAt(i: number, k: number): [number, number, number] {
  const [nx, ny, nz] = DIMS[k];
  const x = i % nx;
  const y = Math.floor(i / nx) % ny;
  const z = Math.floor(i / (nx * ny)) % nz;
  return [
    (x - (nx - 1) / 2) * SPACING,
    (y - (ny - 1) / 2) * SPACING,
    (z - (nz - 1) / 2) * SPACING,
  ];
}

export function lerp3(
  a: [number, number, number],
  b: [number, number, number],
  p: number,
): [number, number, number] {
  return [lerp(a[0], b[0], p), lerp(a[1], b[1], p), lerp(a[2], b[2], p)];
}

export const isTopCube = (i: number) => posAt(i, 6)[1] > 0.01;

export const BASE_SCALE = [1.18, 1.04, 0.96, 0.88, 0.64, 0.58, 0.53];

export function cubeScale(t: number) {
  const {k, p, isTransition} = stageAt(t);
  if (!isTransition) return BASE_SCALE[k];
  return lerp(BASE_SCALE[Math.max(0, k - 1)], BASE_SCALE[k], p);
}

export function camDistance(t: number) {
  const keys: Array<[number, number]> = [
    [0, 6.8],
    [9, 8.2],
    [11.25, 8.8],
    [41, 14.5],
    [60, 11.2],
    [72, 10.4],
    [78.75, 12.8],
    [92, 13.6],
    [103.125, 12.2],
    [118, 11],
    [130, 11.2],
    [150, 13.5],
    [152, 14],
  ];
  for (let i = 0; i < keys.length - 1; i += 1) {
    const [ta, da] = keys[i];
    const [tb, db] = keys[i + 1];
    if (t >= ta && t <= tb) {
      return lerp(da, db, smooth((t - ta) / (tb - ta)));
    }
  }
  return t < keys[0][0] ? keys[0][1] : keys[keys.length - 1][1];
}

export const C = {
  bg: '#05070C',
  ink: '#ECF7FF',
  body: '#C9D8E6',
  muted: '#6E8095',
  cyan: '#5FF3FF',
  teal: '#2BD9C8',
  amber: '#FFB84D',
  red: '#FF5566',
  white: '#FFFFFF',
};
