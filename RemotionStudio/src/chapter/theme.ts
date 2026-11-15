export const C = {
  paper: '#FBFAF7',
  ink: '#252A31',
  muted: '#6B7280',
  orange: '#E8733B',
  orangeSoft: '#FBEEE6',
  graph: '#E9E6DE',
  dark: '#07090D',
  dark2: '#0E1620',
  cyan: '#7AD8E8',
};

export const FONT = '"Segoe UI", Arial, sans-serif';
export const DISPLAY = '"Segoe UI Semibold", "Segoe UI", Arial, sans-serif';

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
export const ease = (v: number) => {
  const p = clamp01(v);
  return p * p * (3 - 2 * p);
};
export const win = (t: number, a: number, b: number, fade = 0.5) =>
  Math.min(ease((t - a) / fade), 1 - ease((t - (b - fade)) / fade));
