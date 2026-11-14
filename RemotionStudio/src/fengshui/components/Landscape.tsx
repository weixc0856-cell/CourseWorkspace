import React, {useMemo} from 'react';
import {P, clamp01, easeOut, lerp, smooth} from '../theme';

export const HORIZON = 1520;
const W = 1080;

const gauss = (x: number, cx: number, w: number) => Math.exp(-(((x - cx) / w) ** 2));

// deterministic wobble so the ink edge is not a pure maths curve
const wobble = (x: number, seed: number) =>
  Math.sin(x * 0.031 + seed) * 2.4 + Math.sin(x * 0.087 + seed * 2.3) * 1.1;

export const ridgeTop = (x: number) => HORIZON - 470 * gauss(x, 566, 268) - 26 * gauss(x, 426, 147) + wobble(x, 1.7);

const path = (fn: (x: number) => number, step = 6) => {
  const pts: string[] = [];
  for (let x = -40; x <= W + 40; x += step) pts.push(`${x.toFixed(1)},${fn(x).toFixed(1)}`);
  return `M${pts.join(' L')}`;
};

const fillPath = (fn: (x: number) => number) => `${path(fn)} L${W + 40},${HORIZON + 1} L-40,${HORIZON + 1} Z`;

const RIDGES = [
  {cx: 812, w: 380, h: 392, seed: 0.4, ink: 0.055, line: 0.16},
  {cx: 250, w: 300, h: 300, seed: 2.9, ink: 0.05, line: 0.14},
];

export const Landscape: React.FC<{
  t: number;
  draw: number;
  farDraw?: number;
  strata?: number;
  riverDraw?: number;
  showRiver?: boolean;
}> = ({t, draw, farDraw = 0, strata = 1, riverDraw = 1, showRiver = true}) => {
  const main = ridgeTop;
  const mainPath = useMemo(() => path(main), []);
  const mainFill = useMemo(() => fillPath(main), []);
  const strataLines = useMemo(() => {
    const out: string[] = [];
    for (let y = 1010; y < HORIZON; y += 19) {
      const pts: string[] = [];
      for (let x = -40; x <= W + 40; x += 10) {
        pts.push(`${x.toFixed(0)},${(y + Math.sin(x * 0.02 + y * 0.11) * 3.2).toFixed(1)}`);
      }
      out.push(`M${pts.join(' L')}`);
    }
    return out;
  }, []);

  return (
    <svg width={W} height={1920} viewBox={`0 0 ${W} 1920`} style={{position: 'absolute', left: 0, top: 0}}>
      <defs>
        <linearGradient id="wash" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={P.ink} stopOpacity={0.1} />
          <stop offset="62%" stopColor={P.ink} stopOpacity={0.035} />
          <stop offset="100%" stopColor={P.paper} stopOpacity={0} />
        </linearGradient>
        <linearGradient id="riverWash" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={P.ink} stopOpacity={0.02} />
          <stop offset="55%" stopColor={P.ink} stopOpacity={0.09} />
          <stop offset="100%" stopColor={P.ink} stopOpacity={0.02} />
        </linearGradient>
        <clipPath id="mainClip">
          <path d={mainFill} />
        </clipPath>
      </defs>

      {RIDGES.map((r, i) => {
        const fn = (x: number) => HORIZON - r.h * gauss(x, r.cx, r.w) + wobble(x, r.seed);
        const len = 1700;
        return (
          <g key={i} opacity={clamp01(farDraw * 1.35 - i * 0.15)}>
            <path d={fillPath(fn)} fill={P.ink} fillOpacity={r.ink} />
            <path
              d={path(fn)}
              fill="none"
              stroke={P.ink}
              strokeWidth={1.4}
              strokeOpacity={r.line}
              strokeDasharray={len}
              strokeDashoffset={len * (1 - easeOut(clamp01(farDraw)))}
              strokeLinecap="round"
            />
          </g>
        );
      })}

      <g opacity={clamp01(draw * 1.8)}>
        <path d={mainFill} fill="url(#wash)" />
        <path
          d={mainPath}
          fill="none"
          stroke={P.ink}
          strokeWidth={2.2}
          strokeOpacity={0.62}
          strokeDasharray={2000}
          strokeDashoffset={2000 * (1 - easeOut(clamp01(draw)))}
          strokeLinecap="round"
        />
        <g clipPath="url(#mainClip)" opacity={strata * (0.72 + 0.28 * Math.sin(t * 0.4))}>
          {strataLines.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={P.ink}
              strokeWidth={1}
              strokeOpacity={0.1 + 0.1 * (1 - (i % 5) / 5)}
            />
          ))}
        </g>
      </g>

      {[0.3, 0.44, 0.6, 0.84].map((u, i) => {
        const x = 300 + u * 470;
        const y = main(x) + 4;
        const s = 0.8 + (i % 3) * 0.16;
        return (
          <g key={i} opacity={clamp01((draw - 0.55) / 0.4) * 0.72}>
            <line x1={x} y1={y} x2={x} y2={y - 10 * s} stroke={P.ink} strokeWidth={1.5} />
            <path
              d={`M${x - 11 * s},${y - 8 * s} L${x},${y - 26 * s} L${x + 11 * s},${y - 8 * s} Z`}
              fill={P.ink}
              fillOpacity={0.18}
              stroke={P.ink}
              strokeWidth={1.1}
            />
            <path
              d={`M${x - 7.5 * s},${y - 18 * s} L${x},${y - 34 * s} L${x + 7.5 * s},${y - 18 * s} Z`}
              fill={P.ink}
              fillOpacity={0.22}
              stroke={P.ink}
              strokeWidth={1}
            />
          </g>
        );
      })}

      <line x1={0} y1={HORIZON} x2={W} y2={HORIZON} stroke={P.ink} strokeOpacity={0.08} strokeWidth={1} />
      {showRiver && <River t={t} draw={riverDraw} />}
    </svg>
  );
};

const River: React.FC<{t: number; draw: number}> = ({t, draw}) => {
  const yBase = 1598;
  const curve = (u: number, off: number) =>
    yBase + off + Math.sin(u * Math.PI * 1.6 + 0.4) * 30 + Math.sin(u * Math.PI * 3.1) * 9;
  const lines = [-58, -34, -12, 10, 32, 54];
  const d = (off: number) => {
    const pts: string[] = [];
    for (let i = 0; i <= 60; i += 1) {
      const u = i / 60;
      pts.push(`${(u * (W + 80) - 40).toFixed(1)},${curve(u, off).toFixed(1)}`);
    }
    return `M${pts.join(' L')}`;
  };
  return (
    <g opacity={clamp01(draw)}>
      <rect x={0} y={1522} width={W} height={150} fill="url(#riverWash)" opacity={0.9} />
      {lines.map((off, i) => {
        const p = easeOut(clamp01(draw * 1.2 - i * 0.12));
        return (
          <g key={i}>
            <path
              d={d(off)}
              fill="none"
              stroke={P.ink}
              strokeWidth={i === 0 || i === lines.length - 1 ? 1.9 : 1.2}
              strokeOpacity={0.2 + 0.22 * Math.sin((Math.PI * (i + 0.5)) / lines.length)}
              strokeDasharray={1400}
              strokeDashoffset={1400 * (1 - p)}
              strokeLinecap="round"
            />
            <path
              d={d(off)}
              fill="none"
              stroke={P.ink}
              strokeWidth={i === 2 || i === 3 ? 2.6 : 1.9}
              strokeOpacity={0.46}
              strokeDasharray="30 150"
              strokeDashoffset={-t * (34 + i * 7)}
              strokeLinecap="round"
            />
          </g>
        );
      })}
    </g>
  );
};

// ---- wind on paper: lines squeeze where the flow accelerates and spread
// ---- behind the ridge; the ratios come from the flow run (2.1x crest, 0.4x lee)
const FLOW = (x: number) =>
  1 + 0.85 * Math.exp(-(((x - 566) / 300) ** 2)) - 0.55 * Math.exp(-(((x - 880) / 340) ** 2));

const squeezeAt = (x: number) => Math.min(1.42, Math.max(0.62, Math.sqrt(0.95 / FLOW(x))));

const LINES = 9;
const SEG = 220;
const FPS = 30;
const END_FRAMES = 4600;

type Poly = {pts: [number, number][]; len: number[]};

const LINES_DATA: Poly[] = (() => {
  const out: Poly[] = [];
  for (let li = 0; li < LINES; li += 1) {
    const off = 44 + li * 33;
    const pts: [number, number][] = [];
    for (let i = 0; i <= SEG; i += 1) {
      const u = i / SEG;
      const x = -30 + u * (W + 60);
      pts.push([x, ridgeTop(x) - off * squeezeAt(x) + Math.sin(u * 9 + li) * 2.4]);
    }
    const len = [0];
    for (let i = 1; i < pts.length; i += 1) {
      len.push(len[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
    }
    out.push({pts, len});
  }
  return out;
})();

const sampleX = (poly: Poly, s: number) => {
  const {pts, len} = poly;
  let lo = 0;
  let hi = len.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (len[mid] < s) lo = mid + 1;
    else hi = mid;
  }
  return pts[Math.min(lo, pts.length - 1)][0];
};

const samplePt = (poly: Poly, s: number): [number, number] => {
  const {pts, len} = poly;
  let lo = 0;
  let hi = len.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (len[mid] < s) lo = mid + 1;
    else hi = mid;
  }
  const i = Math.max(1, lo);
  const span = len[i] - len[i - 1];
  const f = span > 0 ? (s - len[i - 1]) / span : 0;
  return [lerp(pts[i - 1][0], pts[i][0], f), lerp(pts[i - 1][1], pts[i][1], f)];
};

// particle positions baked once: TABLE[frame][particle]
const TABLE: [number, number][][] = (() => {
  const seeds: {line: number; s: number}[] = [];
  for (let li = 0; li < LINES; li += 1) {
    const total = LINES_DATA[li].len[LINES_DATA[li].len.length - 1];
    for (let k = 0; k < 5; k += 1) seeds.push({line: li, s: (total * (k + li * 0.37)) / 5});
  }
  const dt = 1 / FPS;
  const out: [number, number][][] = [];
  const s = seeds.map((x) => x.s);
  for (let f = 0; f <= END_FRAMES; f += 1) {
    const row: [number, number][] = [];
    for (let i = 0; i < seeds.length; i += 1) {
      const poly = LINES_DATA[seeds[i].line];
      const total = poly.len[poly.len.length - 1];
      row.push(samplePt(poly, s[i]));
      s[i] += dt * 135 * clamp01(0.55 + FLOW(sampleX(poly, s[i])) * 0.42);
      if (s[i] > total) s[i] -= total;
    }
    out.push(row);
  }
  return out;
})();

export const WindPaper: React.FC<{t: number; opacity: number}> = ({t, opacity}) => {
  const f = Math.min(END_FRAMES, Math.max(0, Math.round(t * FPS)));
  const positions = TABLE[f];
  return (
    <g opacity={opacity}>
      {LINES_DATA.map((line, i) => (
        <path
          key={i}
          d={`M${line.pts.map((p) => `${p[0].toFixed(0)},${p[1].toFixed(0)}`).join(' L')}`}
          fill="none"
          stroke={P.ink}
          strokeWidth={1}
          strokeOpacity={0.09 + 0.02 * (i % 3)}
        />
      ))}
      {positions.map((q, i) => (
        <g key={i}>
          <circle cx={q[0]} cy={q[1]} r={1.9} fill={P.ink} opacity={0.45} />
          <line
            x1={q[0] - 9}
            y1={q[1]}
            x2={q[0]}
            y2={q[1]}
            stroke={P.cinnabar}
            strokeWidth={1.3}
            strokeOpacity={0.5}
            strokeLinecap="round"
          />
        </g>
      ))}
    </g>
  );
};

export const Village: React.FC<{p: number}> = ({p}) => {
  if (p <= 0) return null;
  const items = [
    {x: 470, y: 1492, s: 1},
    {x: 528, y: 1500, s: 0.86},
    {x: 586, y: 1494, s: 0.94},
  ];
  return (
    <g opacity={clamp01(p)}>
      {items.map((it, i) => {
        const q = clamp01(p * 1.5 - i * 0.2);
        return (
          <g key={i} opacity={q}>
            <path
              d={`M${it.x - 26 * it.s},${it.y} L${it.x},${it.y - 16 * it.s} L${it.x + 26 * it.s},${it.y} Z`}
              fill="none"
              stroke={P.ink}
              strokeWidth={1.8}
            />
            <rect
              x={it.x - 19 * it.s}
              y={it.y}
              width={38 * it.s}
              height={16 * it.s}
              fill="none"
              stroke={P.ink}
              strokeWidth={1.3}
            />
          </g>
        );
      })}
      <circle cx={528} cy={1544} r={3.4} fill={P.cinnabar} opacity={clamp01(p * 1.4)} />
    </g>
  );
};
