import React from 'react';
import {C, DISPLAY, FPS, SANS, clamp01, easeOut, mulberry32} from '../theme';

export const HookVisual: React.FC<{progress: number; t: number}> = ({progress, t}) => {
  const zoom = 1 + 3.4 * easeOut((progress - 0.28) / 0.62);
  const detail = clamp01(1 - (zoom - 1.7) / 1.3);
  const cx = 540;
  const cy = 1000;
  const fadeLabels = clamp01(1 - (progress - 0.18) / 0.3);
  const rand = mulberry32(42);
  const cells = new Array(14 * 14).fill(0).map(() => rand());
  return (
    <svg viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
      <defs>
        <radialGradient id="chipGlow">
          <stop offset="0%" stopColor={C.cyan} stopOpacity="0.55" />
          <stop offset="60%" stopColor={C.cyan} stopOpacity="0.08" />
          <stop offset="100%" stopColor={C.cyan} stopOpacity="0" />
        </radialGradient>
        <linearGradient id="screenGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0B1A24" />
          <stop offset="100%" stopColor="#05090E" />
        </linearGradient>
        <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="10" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g transform={`translate(${cx} ${cy}) scale(${zoom}) translate(${-cx} ${-cy})`}>
        <circle cx={cx} cy={cy} r={420} fill="url(#chipGlow)" opacity={0.6} />
        <g opacity={detail}>
          <rect x={352} y={640} width={376} height={740} rx={54} fill="#070C12" stroke="#335062" strokeWidth={3} />
          <rect x={372} y={664} width={336} height={692} rx={38} fill="url(#screenGrad)" stroke="#1E3442" strokeWidth={1.5} />
          <g opacity={0.55}>
            {new Array(9).fill(0).map((_, i) => (
              <line key={`h${i}`} x1={400} y1={720 + i * 68} x2={680} y2={720 + i * 68} stroke="#1A3240" strokeWidth={1} />
            ))}
          </g>
        </g>
        <g>
          <rect x={440} y={890} width={200} height={200} rx={16} fill="#08161E" stroke={C.cyan} strokeWidth={1.6} />
          {cells.map((v, i) => {
            const gx = i % 14;
            const gy = Math.floor(i / 14);
            if (v < 0.52) return null;
            return (
              <rect
                key={i}
                x={446 + gx * 13.4}
                y={896 + gy * 13.4}
                width={10.5}
                height={10.5}
                fill={v > 0.92 ? C.cyan : '#1E5A6A'}
                opacity={v > 0.92 ? 0.95 : 0.55}
              />
            );
          })}
          <rect x={504} y={954} width={72} height={72} rx={8} fill="none" stroke={C.white} strokeWidth={1.4} opacity={0.85} />
          <circle cx={540} cy={990} r={26} fill={C.cyan} opacity={0.32} filter="url(#softGlow)" />
        </g>
        <g opacity={0.75 * detail} stroke={C.cyan} fill="none">
          {[250, 300, 350].map((r, i) => (
            <circle key={i} cx={cx} cy={990} r={r} strokeDasharray={i === 1 ? '3 8' : '1 10'} strokeWidth={1.2} opacity={0.5 - i * 0.1} />
          ))}
        </g>
        <g transform={`rotate(${t * 34} ${cx} 990)`} opacity={0.8 * detail}>
          <line x1={cx} y1={990} x2={cx + 330} y2={990} stroke={C.cyan} strokeWidth={1.4} opacity={0.55} />
        </g>
        <g opacity={fadeLabels * detail}>
          {[
            {x: 540, y: 860, label: '20B TRANSISTORS', side: 1},
            {x: 700, y: 1040, label: '3 NM CLASS', side: 1},
            {x: 540, y: 1230, label: '300 MM WAFER', side: -1},
          ].map((L, i) => (
            <g key={i} opacity={0.8}>
              <line x1={L.x} y1={L.y} x2={L.x + (L.side > 0 ? 90 : -90)} y2={L.y - 26} stroke={C.muted} strokeWidth={1} />
              <circle cx={L.x} cy={L.y} r={3} fill={C.cyan} />
              <text
                x={L.x + (L.side > 0 ? 98 : -98)}
                y={L.y - 30}
                fill={C.body}
                fontFamily={DISPLAY}
                fontWeight={800}
                fontSize={17}
                letterSpacing={2}
                textAnchor={L.side > 0 ? 'start' : 'end'}
              >
                {L.label}
              </text>
            </g>
          ))}
        </g>
      </g>
    </svg>
  );
};

const SCALE_LABELS = ['1 mm', '100 µm', '10 µm', '1 µm', '100 nm', '10 nm', '3 nm'];
const SCALE_SIZES = [880, 620, 430, 292, 194, 124, 72];

export const ScaleVisual: React.FC<{progress: number}> = ({progress}) => {
  const zoom = Math.pow(1.55, progress * 5);
  const active = Math.min(6, Math.floor(progress * 6.999));
  const cx = 540;
  const cy = 1010;
  return (
    <svg viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
      <defs>
        <radialGradient id="scaleGlow">
          <stop offset="0%" stopColor={C.violet} stopOpacity="0.5" />
          <stop offset="100%" stopColor={C.violet} stopOpacity="0" />
        </radialGradient>
        <filter id="gateGlow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="8" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <circle cx={cx} cy={cy} r={440} fill="url(#scaleGlow)" opacity={0.55} />
      <g transform={`translate(${cx} ${cy}) scale(${zoom}) translate(${-cx} ${-cy})`}>
        {SCALE_SIZES.map((s, i) => (
          <rect
            key={i}
            x={cx - s / 2}
            y={cy - s / 2}
            width={s}
            height={s}
            rx={s * 0.06}
            fill="none"
            stroke={i === active ? C.violet : 'rgba(139,92,255,0.32)'}
            strokeWidth={i === active ? 2 : 1}
            vectorEffect="non-scaling-stroke"
            opacity={i <= active ? 1 : 0.35}
          />
        ))}
      </g>
      <g transform={`translate(${cx} ${cy})`}>
        <rect x={-34} y={-6} width={68} height={12} rx={2} fill={C.cyan} opacity={0.26} filter="url(#gateGlow)" />
        <rect x={-30} y={-5} width={60} height={10} rx={1} fill={C.cyan} opacity={0.9} />
        <rect x={-26} y={8} width={52} height={4} fill={C.violet} opacity={0.9} />
        <rect x={-26} y={-16} width={52} height={4} fill={C.amber} opacity={0.75} />
        <circle cx={0} cy={0} r={40} fill={C.cyan} opacity={0.08} />
      </g>
      <g>
        {SCALE_LABELS.map((l, i) => {
          const on = i === active;
          return (
            <g key={i} opacity={on ? 1 : 0.28}>
              <line x1={72} y1={700 + i * 92} x2={on ? 118 : 96} y2={700 + i * 92} stroke={on ? C.violet : C.faint} strokeWidth={on ? 2 : 1} />
              <text
                x={132}
                y={706 + i * 92}
                fill={on ? C.ink : C.muted}
                fontFamily={DISPLAY}
                fontWeight={on ? 900 : 500}
                fontSize={on ? 26 : 20}
                letterSpacing={2}
              >
                {l}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
};

export const DepthGauge: React.FC<{cells: number; color?: string; label?: string; max?: number; bottom?: number}> = ({
  cells,
  color = C.cyan,
  label = 'ETCH DEPTH',
  max = 130,
  bottom = 84,
}) => {
  const p = clamp01(cells / max);
  const nm = Math.round(420 * p);
  return (
    <div style={{position: 'absolute', left: 96, right: 96, bottom}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 10}}>
        <div style={{fontFamily: DISPLAY, fontWeight: 800, fontSize: 17, letterSpacing: '0.24em', color: C.muted}}>
          {label}
        </div>
        <div style={{fontFamily: DISPLAY, fontWeight: 900, fontSize: 34, letterSpacing: '0.02em', color}}>
          {nm}
          <span style={{fontSize: 18, marginLeft: 6, color: C.muted}}>nm</span>
        </div>
      </div>
      <div style={{position: 'relative', height: 10, background: 'rgba(255,255,255,0.08)', borderRadius: 5, overflow: 'hidden'}}>
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            bottom: 0,
            width: `${p * 100}%`,
            background: `linear-gradient(90deg, ${color}55, ${color})`,
            boxShadow: `0 0 18px ${color}`,
            borderRadius: 5,
          }}
        />
        {new Array(11).fill(0).map((_, i) => (
          <div key={i} style={{position: 'absolute', left: `${i * 10}%`, top: 0, bottom: 0, width: 1, background: 'rgba(5,7,12,0.55)'}} />
        ))}
      </div>
    </div>
  );
};

export const GasPulse: React.FC<{t: number; color?: string}> = ({t, color = C.cyan}) => {
  const phase = Math.floor(t / 1.875) % 2;
  const beat = ((t * 128) / 60) % 1;
  const pulse = Math.exp(-beat * 8);
  return (
    <div style={{display: 'flex', alignItems: 'center', gap: 12}}>
      {['SF6', 'C4F8'].map((g, i) => {
        const on = i === phase;
        const c = i === 0 ? color : C.pink;
        return (
          <div
            key={g}
            style={{
              padding: '10px 18px',
              borderRadius: 999,
              border: `1px solid ${on ? c : 'rgba(255,255,255,0.14)'}`,
              background: on ? `${c}1F` : 'rgba(255,255,255,0.02)',
              boxShadow: on ? `0 0 24px ${c}55` : 'none',
              fontFamily: DISPLAY,
              fontWeight: 800,
              fontSize: 18,
              letterSpacing: '0.18em',
              color: on ? c : C.muted,
              transform: on ? `scale(${1 + pulse * 0.06})` : 'scale(1)',
            }}
          >
            {g}
          </div>
        );
      })}
    </div>
  );
};

export const Callout: React.FC<{
  x: number;
  y: number;
  dx: number;
  dy: number;
  text: string;
  color?: string;
  delay?: number;
  progress: number;
  size?: number;
  boxW?: number;
}> = ({x, y, dx, dy, text, color = C.cyan, delay = 0, progress, size = 6.4, boxW = 52}) => {
  const p = clamp01((progress - delay) / 0.18);
  const lx = x + dx;
  const ly = y + dy;
  return (
    <g opacity={p}>
      <circle cx={x} cy={y} r={2.4} fill={color} />
      <circle cx={x} cy={y} r={5.5} fill="none" stroke={color} strokeWidth={0.8} opacity={0.5} />
      <line x1={x} y1={y} x2={lx} y2={ly} stroke={color} strokeWidth={0.9} strokeDasharray="3 2" opacity={0.85} />
      <rect x={lx - boxW / 2} y={ly - 7} width={boxW} height={13} rx={2} fill="#05070C" stroke={color} strokeWidth={0.6} opacity={0.92} />
      <text x={lx} y={ly + 2} fill={color} fontFamily={DISPLAY} fontWeight={800} fontSize={size} letterSpacing={0.9} textAnchor="middle">
        {text}
      </text>
    </g>
  );
};

export const PanelLabel: React.FC<{
  x: number;
  y: number;
  text: string;
  color: string;
  size?: number;
}> = ({x, y, text, color, size = 6.2}) => {
  const w = text.length * size * 0.6 + 8;
  return (
    <g>
      <rect x={x - 3} y={y - size - 2.5} width={w} height={size + 6} rx={1.5} fill="#05070C" opacity={0.85} />
      <text x={x} y={y} fill={color} fontFamily={DISPLAY} fontWeight={800} fontSize={size} letterSpacing={0.9}>
        {text}
      </text>
    </g>
  );
};

export const DeepTrench: React.FC<{progress: number; t: number}> = ({progress, t}) => {
  const depthP = easeOut(progress / 0.75);
  const top = 720;
  const yBottom = 780 + 740 * depthP;
  const x0 = 360;
  const x1 = 560;
  const rand = mulberry32(77);
  const ions = new Array(46).fill(0).map(() => {
    const x = x0 + 12 + rand() * (x1 - x0 - 24);
    const speed = 0.5 + rand() * 0.6;
    const y = top + ((t * speed * 260 + rand() * 800) % (yBottom - top + 80));
    return {x, y, len: 16 + rand() * 46, o: 0.12 + rand() * 0.25};
  });
  const layers = 200;
  const stackTop = 770;
  const stackH = 720;
  return (
    <svg viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
      <defs>
        <linearGradient id="trenchGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0B2530" />
          <stop offset="100%" stopColor="#041015" />
        </linearGradient>
        <linearGradient id="layerGrad" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={C.violet} stopOpacity="0.08" />
          <stop offset="100%" stopColor={C.cyan} stopOpacity="0.55" />
        </linearGradient>
        <filter id="deepGlow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="7" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <rect x={x0} y={top} width={x1 - x0} height={yBottom - top} fill="url(#trenchGrad)" />
      {ions.map((p, i) => (
        <line
          key={i}
          x1={p.x}
          y1={p.y - p.len}
          x2={p.x}
          y2={p.y}
          stroke={C.cyan}
          strokeWidth={0.8}
          opacity={p.o}
          strokeLinecap="round"
        />
      ))}
      <rect x={x0} y={top} width={3} height={yBottom - top} fill={C.teal} opacity={0.9} filter="url(#deepGlow)" />
      <rect x={x1 - 3} y={top} width={3} height={yBottom - top} fill={C.teal} opacity={0.9} filter="url(#deepGlow)" />
      <rect x={x0} y={yBottom - 4} width={x1 - x0} height={4} fill={C.cyan} opacity={0.9} filter="url(#deepGlow)" />
      <ellipse cx={(x0 + x1) / 2} cy={yBottom + 4} rx={90} ry={18} fill={C.cyan} opacity={0.14} filter="url(#deepGlow)" />

      <g opacity={0.5}>
        {new Array(12).fill(0).map((_, i) => (
          <line
            key={i}
            x1={x0 + 6}
            y1={top + 40 + i * 62}
            x2={x1 - 6}
            y2={top + 40 + i * 62}
            stroke={C.muted}
            strokeWidth={0.6}
            strokeDasharray="2 6"
          />
        ))}
      </g>

      {/* dimension lines */}
      <g opacity={0.55} stroke={C.cyan} strokeWidth={1}>
        <line x1={x0 - 34} y1={top} x2={x0 - 34} y2={yBottom} />
        <line x1={x0 - 40} y1={top} x2={x0 - 28} y2={top} />
        <line x1={x0 - 40} y1={yBottom} x2={x0 - 28} y2={yBottom} />
        <line x1={x0} y1={top - 26} x2={x1} y2={top - 26} />
        <line x1={x0} y1={top - 32} x2={x0} y2={top - 20} />
        <line x1={x1} y1={top - 32} x2={x1} y2={top - 20} />
      </g>
      <text x={x0 - 46} y={(top + yBottom) / 2} fill={C.cyan} fontFamily={DISPLAY} fontWeight={800} fontSize={16} letterSpacing={2} textAnchor="middle" transform={`rotate(-90 ${x0 - 46} ${(top + yBottom) / 2})`}>
        DEPTH
      </text>
      <text x={(x0 + x1) / 2} y={top - 36} fill={C.cyan} fontFamily={DISPLAY} fontWeight={800} fontSize={15} letterSpacing={2} textAnchor="middle">
        WIDTH W
      </text>

      {/* 200-layer stack */}
      <g transform={`translate(700 ${stackTop})`}>
        {new Array(layers).fill(0).map((_, i) => {
          const on = i / layers <= progress;
          const y = (i / layers) * stackH;
          return (
            <g key={i} opacity={on ? 0.55 + (i % 5) * 0.06 : 0.06}>
              <rect x={0} y={y} width={270} height={2.4} fill="url(#layerGrad)" />
            </g>
          );
        })}
        <rect x={-16} y={0} width={2} height={stackH} fill={C.violet} opacity={0.5} />
        <text x={0} y={-20} fill={C.violet} fontFamily={DISPLAY} fontWeight={800} fontSize={17} letterSpacing={2}>
          200 LAYERS
        </text>
      </g>

      <rect x={300} y={1920 * ((t * 0.35) % 1)} width={560} height={2} fill={C.cyan} opacity={0.14} />
    </svg>
  );
};

export const ChipMacro: React.FC<{progress: number; t: number}> = ({progress, t}) => {
  const rand = mulberry32(2026);
  const traces = new Array(26).fill(0).map(() => {
    const x = 140 + rand() * 800;
    const y = 720 + rand() * 620;
    const pts = [0, 1, 2, 3].map((k) => [x + k * (18 + rand() * 34), y + (rand() - 0.5) * 50]);
    return pts.map((p) => p.join(',')).join(' ');
  });
  return (
    <svg viewBox="0 0 1080 1920" style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}>
      <defs>
        <radialGradient id="dieGlow">
          <stop offset="0%" stopColor={C.cyan} stopOpacity="0.3" />
          <stop offset="100%" stopColor={C.cyan} stopOpacity="0" />
        </radialGradient>
        <filter id="macroGlow" x="-40%" y="-40%" width="180%" height="180%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge>
            <feMergeNode in="b" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <circle cx={540} cy={1030} r={430} fill="url(#dieGlow)" />
      <circle cx={540} cy={1030} r={360} fill="#081018" stroke="#264E5C" strokeWidth={2} />
      {[300, 240, 180].map((r, i) => (
        <circle key={i} cx={540} cy={1030} r={r} fill="none" stroke={C.cyan} strokeWidth={0.7} opacity={0.16} strokeDasharray="2 9" />
      ))}
      <rect x={380} y={870} width={320} height={320} rx={18} fill="#071219" stroke={C.cyan} strokeWidth={1.6} />
      {new Array(9).fill(0).map((_, i) => (
        <g key={i} opacity={0.4}>
          <line x1={388} y1={880 + i * 38} x2={692} y2={880 + i * 38} stroke={C.cyan} strokeWidth={0.5} />
          <line x1={388 + i * 38} y1={880} x2={388 + i * 38} y2={1190} stroke={C.cyan} strokeWidth={0.5} />
        </g>
      ))}
      <g filter="url(#macroGlow)" opacity={0.8}>
        {traces.map((p, i) => (
          <polyline key={i} points={p} fill="none" stroke={i % 4 === 0 ? C.amber : C.cyan} strokeWidth={1.2} opacity={0.55} />
        ))}
      </g>
      <rect x={540} y={890} width={2} height={280} fill={C.white} opacity={0.5 * (1 - progress)} />
      <g opacity={Math.min(1, progress * 3)}>
        <text x={540} y={1260} fill={C.ink} fontFamily={DISPLAY} fontWeight={900} fontSize={40} letterSpacing={4} textAnchor="middle">
          20B TRANSISTORS
        </text>
        <text x={540} y={1300} fill={C.muted} fontFamily={DISPLAY} fontWeight={600} fontSize={19} letterSpacing={4} textAnchor="middle">
          ONE DIE · 300 MM WAFER
        </text>
      </g>
    </svg>
  );
};

export const CalloutLayer: React.FC<{viewBox: number[]; children: React.ReactNode}> = ({
  viewBox,
  children,
}) => (
  <svg
    viewBox={viewBox.join(' ')}
    style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}
  >
    {children}
  </svg>
);

export const MetricBar: React.FC<{
  label: string;
  value: number;
  max: number;
  color: string;
  suffix?: string;
  width?: number;
}> = ({label, value, max, color, suffix = 'nm', width = 100}) => {
  const p = clamp01(value / max);
  return (
    <div style={{width, fontFamily: DISPLAY}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 6}}>
        <span style={{fontSize: 15, letterSpacing: '0.18em', color: C.muted, fontWeight: 800}}>{label}</span>
        <span style={{fontSize: 22, color, fontWeight: 900}}>
          {Math.round(value)}
          <span style={{fontSize: 12, color: C.muted, marginLeft: 3}}>{suffix}</span>
        </span>
      </div>
      <div style={{height: 6, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden'}}>
        <div style={{height: '100%', width: `${p * 100}%`, background: color, boxShadow: `0 0 12px ${color}`, borderRadius: 3}} />
      </div>
    </div>
  );
};
