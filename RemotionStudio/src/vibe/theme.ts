import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const DISPLAY = 'JostVibe';
export const SANS = 'NotoSCVibe';

loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-900-normal.woff2'), weight: '900'});
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-800-normal.woff2'), weight: '800'});
loadFont({family: DISPLAY, url: staticFile('fonts/jost-latin-300-normal.woff2'), weight: '300'});
loadFont({
  family: SANS,
  url: staticFile('fonts/noto-sans-sc-chinese-simplified-400-normal.woff2'),
  weight: '400',
});
loadFont({
  family: SANS,
  url: staticFile('fonts/noto-sans-sc-latin-400-normal.woff2'),
  weight: '400',
});

export const C = {
  bg: '#05070C',
  bg2: '#08111A',
  ink: '#ECF7FF',
  body: '#C9D8E6',
  muted: '#6E8095',
  faint: '#263444',
  cyan: '#5FF3FF',
  teal: '#2BD9C8',
  violet: '#8B5CFF',
  amber: '#FFB84D',
  pink: '#FF4D9D',
  red: '#FF5566',
  white: '#FFFFFF',
};

export const FPS = 30;
export const W = 1080;
export const H = 1920;
export const BPM = 128;
export const BEAT_OFFSET = 0.384;

export const beatPhase = (t: number) => {
  const v = ((t - BEAT_OFFSET) * BPM) / 60;
  return ((v % 1) + 1) % 1;
};

export const beatPulse = (t: number, decay = 7) => Math.exp(-beatPhase(t) * decay);

export const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

export const easeOut = (v: number) => 1 - Math.pow(1 - clamp01(v), 3);

export const mix = (a: number, b: number, t: number) => a + (b - a) * clamp01(t);

export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const panel = {
  left: 64,
  right: 64,
  top: 690,
  height: 690,
};

export const caps = {
  left: 80,
  right: 80,
  top: 1500,
};
