import React, {useMemo} from 'react';
import {P, FPS, clamp01} from '../theme';
import {HORIZON, Path, buildPaths, samplePath, speedAt} from '../camera';

const SEEDS = [1220, 1176, 1132, 1088, 1044, 1000, 956, 912, 868, 824, 780, 736, 692];
const PATHS: Path[] = buildPaths(SEEDS);
const PER_PATH = 5;
const TRAIL = 78;
const END = 4600;

type Particle = {path: number; s0: number};

const PARTICLES: Particle[] = (() => {
  const out: Particle[] = [];
  for (let i = 0; i < PATHS.length; i += 1) {
    const total = (PATHS[i].pts.length - 1) * 4;
    for (let k = 0; k < PER_PATH; k += 1) out.push({path: i, s0: (total * (k + i * 0.37)) / PER_PATH});
  }
  return out;
})();

// bake arc length per frame so the film stays a pure function of t
const S_TABLE: Float32Array[] = (() => {
  const dt = 1 / FPS;
  const s = PARTICLES.map((p) => p.s0);
  const table: Float32Array[] = [];
  for (let f = 0; f <= END; f += 1) {
    table.push(Float32Array.from(s));
    for (let i = 0; i < PARTICLES.length; i += 1) {
      const path = PATHS[PARTICLES[i].path];
      const total = (path.pts.length - 1) * 4;
      const [x, y] = samplePath(path, s[i]);
      const v = speedAt(x, y);
      s[i] += dt * 62 * clamp01(0.35 + v * 0.75);
      if (s[i] > total) s[i] -= total;
    }
  }
  return table;
})();

export const WindParticles: React.FC<{t: number; opacity: number}> = ({t, opacity}) => {
  const f = Math.min(END, Math.max(0, Math.round(t * FPS)));
  const s = S_TABLE[f];
  return (
    <g opacity={opacity}>
      {PARTICLES.map((p, i) => {
        const path = PATHS[p.path];
        const total = (path.pts.length - 1) * 4;
        const head = s[i];
        const from = Math.max(0, head - TRAIL);
        const pts: string[] = [];
        for (let a = from; a <= head; a += 6) {
          const [x, y] = samplePath(path, a);
          pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
        }
        const [hx, hy] = samplePath(path, head);
        const v = speedAt(hx, hy);
        const hot = clamp01((v - 1.35) / 0.8);
        const near = head > total - 40 ? (total - head) / 40 : 1;
        const fade = head < 30 ? head / 30 : 1;
        const op = 0.55 * near * fade;
        const color = hot > 0.15 ? P.cinnabar : P.ink;
        return (
          <g key={i} opacity={op}>
            <polyline
              points={pts.join(' ')}
              fill="none"
              stroke={hot > 0.15 ? P.cinnabar : P.inkSoft}
              strokeWidth={1.6 + hot * 1.4}
              strokeOpacity={0.28 + hot * 0.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <circle cx={hx} cy={hy} r={2.2 + hot * 1.6} fill={color} opacity={0.6 + hot * 0.4} />
          </g>
        );
      })}
      {/* faint guide lines so the field reads even between gusts */}
      {PATHS.map((path, i) => (
        <polyline
          key={`g${i}`}
          points={path.pts
            .filter((_, k) => k % 3 === 0)
            .map(([x, y]) => `${x.toFixed(0)},${y.toFixed(0)}`)
            .join(' ')}
          fill="none"
          stroke={P.ink}
          strokeWidth={0.8}
          strokeOpacity={0.06}
        />
      ))}
      <line x1={-60} y1={HORIZON} x2={1180} y2={HORIZON} stroke={P.ink} strokeOpacity={0.05} strokeWidth={1} />
    </g>
  );
};
