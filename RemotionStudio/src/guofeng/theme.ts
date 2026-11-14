import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const DISPLAY = 'GFDisplay';
export const SANS = 'GFSans';
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-900-normal.woff2'), weight: '900'});
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-800-normal.woff2'), weight: '800'});
loadFont({family: SANS, url: staticFile('fonts/noto-sans-sc-chinese-simplified-400-normal.woff2'), weight: '400'});

export const W = 1080;
export const H = 1920;
export const FPS = 30;
export const DUR = 300; // 10 s

export const C = {
  skyTop: '#08161d',
  skyMid: '#123039',
  skyLow: '#2b4c4c',
  sun: '#c8452f',
  sunHalo: '#e08a5a',
  far: '#1a3a42',
  mid: '#14303a',
  near: '#0a1a20',
  cliff: '#050f13',
  river: '#1d4049',
  riverHi: '#4e8a86',
  paper: '#f2e9d8',
  gold: '#e0a45c',
  ink: '#050d10',
};

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
export const easeOut = (v: number) => 1 - Math.pow(1 - clamp01(v), 3);
export const smooth = (v: number) => {
  const x = clamp01(v);
  return x * x * (3 - 2 * x);
};
export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const seg = (t: number, a: number, b: number) => clamp01((t - a) / Math.max(0.001, b - a));
