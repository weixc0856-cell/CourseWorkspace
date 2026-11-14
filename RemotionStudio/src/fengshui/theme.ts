import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const DISPLAY = 'FengDisplay';
export const SANS = 'FengSans';

loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-900-normal.woff2'), weight: '900'});
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-800-normal.woff2'), weight: '800'});
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-300-normal.woff2'), weight: '300'});
loadFont({family: SANS, url: staticFile('fonts/noto-sans-sc-chinese-simplified-400-normal.woff2'), weight: '400'});
loadFont({family: SANS, url: staticFile('fonts/noto-sans-sc-latin-400-normal.woff2'), weight: '400'});

export const W = 1080;
export const H = 1920;
export const FPS = 30;
export const DURATION = 152;

// Music: Guzheng Morning (Antti Luode), 126.01 BPM measured; bar = 1.90476 s.
export const BPM = 126.01;
export const BEAT = 60 / BPM;
export const BAR = BEAT * 4;
export const BARS = 80;

export const P = {
  paper: '#F5F0E6',
  paperDeep: '#EAE0CD',
  paperEdge: '#DCD1B9',
  ink: '#2E3E42',
  inkSoft: '#5C6C6E',
  inkFaint: '#9AA096',
  faint: '#BFB6A2',
  cinnabar: '#A6402C',
  cinnabarDeep: '#8A3323',
  wash: '#D9D2C0',
  dark: '#0E1418',
  darkInk: '#E9E3D5',
  darkFaint: '#5E6A6C',
  cold: '#7FA8A0',
  warm: '#E0A05A',
};

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
export const easeOut = (v: number) => 1 - Math.pow(1 - clamp01(v), 3);
export const easeIn = (v: number) => Math.pow(clamp01(v), 3);
export const smooth = (v: number) => {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
};
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
export const seg = (t: number, a: number, b: number) => clamp01((t - a) / (b - a));
export const segS = (t: number, a: number, b: number) => smooth((t - a) / (b - a));

export const barTime = (k: number) => k * BAR;
export const beatPulse = (t: number, decay = 6) => {
  const phase = ((t / BEAT) % 1 + 1) % 1;
  return Math.exp(-phase * decay);
};
