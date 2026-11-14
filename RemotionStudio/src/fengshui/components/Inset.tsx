import React, {useMemo} from 'react';
import {Img, staticFile, useCurrentFrame} from 'remotion';
import {P, DISPLAY, FPS, clamp01, easeOut} from '../theme';
import fig from '../figure.json';

const DATA = fig as unknown as {
  crop: {x0: number; x1: number; z0: number; z1: number};
  img: {w: number; h: number};
  streamlines: number[][][];
  terrain: number[][];
  profile: {x: number[]; speed: number[]; lev: number};
  ratios: {upwind: number; crest: number; lee: number; hill_x: number; hill_h: number};
};

const mapX = (x: number, w: number) => ((x - DATA.crop.x0) / (DATA.crop.x1 - DATA.crop.x0)) * w;
const mapY = (z: number, h: number) => h - ((z - DATA.crop.z0) / (DATA.crop.z1 - DATA.crop.z0)) * h;

const mix = (a: number[], b: number[], t: number) => a.map((v, i) => v + (b[i] - v) * clamp01(t));

export const SimPanel: React.FC<{
  start: number;
  chartStart: number;
  x?: number;
  y?: number;
  w?: number;
}> = ({start, chartStart, x = 84, y = 330, w = 912}) => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const p = easeOut(clamp01((t - start) / 0.7));
  if (p <= 0) return null;

  const fieldH = (w * DATA.img.h) / DATA.img.w;
  const chartFull = 232;
  const chartOpen = easeOut(clamp01((t - chartStart) / 0.9));
  const chartH = chartFull * chartOpen;
  const h = fieldH + chartH + (chartOpen > 0.02 ? 1 : 0);

  const terrainPath = useMemo(() => {
    const pts = DATA.terrain.map(([tx, th]) => `${mapX(tx, w).toFixed(1)},${mapY(th, fieldH).toFixed(1)}`);
    return `M${pts.join(' L')} L${w},${fieldH} L0,${fieldH} Z`;
  }, [w, fieldH]);

  const lines = useMemo(
    () =>
      DATA.streamlines.map((pts) => {
        const d = pts
          .filter((_, i) => i % 2 === 0)
          .map(([sx, sz]) => `${mapX(sx, w).toFixed(1)},${mapY(sz, fieldH).toFixed(1)}`);
        return `M${d.join(' L')}`;
      }),
    [w, fieldH],
  );

  const draw = easeOut(clamp01((t - start - 0.25) / 1.5));

  // chart geometry
  const cp = DATA.profile;
  const xmin = cp.x[0];
  const xmax = cp.x[cp.x.length - 1];
  const ymax = 2.3;
  const padL = 54;
  const padR = 26;
  const cw = w - padL - padR;
  const px = (v: number) => padL + ((v - xmin) / (xmax - xmin)) * cw;
  const py = (v: number) => chartFull - 46 - (v / ymax) * (chartFull - 78);
  const cq = clamp01((t - chartStart) / 1.4);
  const count = Math.max(2, Math.floor(cp.x.length * easeOut(cq)));
  const curve = `M${cp.x
    .slice(0, count)
    .map((vx, i) => `${px(vx).toFixed(1)},${py(cp.speed[i]).toFixed(1)}`)
    .join(' L')}`;
  const crestX = px(DATA.ratios.hill_x);

  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        opacity: p,
        transform: `translateY(${(1 - p) * 20}px)`,
        background: P.dark,
        boxShadow: '0 26px 64px rgba(46,62,66,0.22)',
      }}
    >
      <div style={{position: 'absolute', left: 0, top: 0, width: w, height: fieldH, overflow: 'hidden'}}>
        <Img src={staticFile('fengshui/sim_field.png')} style={{position: 'absolute', inset: 0, width: w, height: fieldH}} />
        <svg width={w} height={fieldH} viewBox={`0 0 ${w} ${fieldH}`} style={{position: 'absolute', left: 0, top: 0}}>
          <path d={terrainPath} fill={P.dark} />
          {lines.map((d, i) => (
            <path
              key={i}
              d={d}
              fill="none"
              stroke={P.darkInk}
              strokeWidth={i % 2 === 0 ? 1.1 : 0.8}
              strokeOpacity={0.4}
              strokeDasharray="700"
              strokeDashoffset={700 * (1 - draw)}
              strokeLinecap="round"
            />
          ))}
          <path d={terrainPath} fill="none" stroke={P.darkInk} strokeWidth={1.5} strokeOpacity={0.8} />
          <circle
            cx={mapX(DATA.ratios.hill_x + 0.2 + ((t * 1.1) % 3.2), w)}
            cy={mapY(DATA.ratios.hill_h + 0.42, fieldH)}
            r={3}
            fill={P.warm}
            opacity={0.9}
          />
        </svg>
        <div
          style={{
            position: 'absolute',
            left: 22,
            top: 16,
            fontFamily: DISPLAY,
            fontSize: 16,
            letterSpacing: '0.2em',
            color: P.darkInk,
            opacity: 0.7,
          }}
        >
          SIMULATION · 2D STEADY FLOW
        </div>
        <div
          style={{
            position: 'absolute',
            right: 22,
            top: 16,
            fontFamily: DISPLAY,
            fontSize: 16,
            letterSpacing: '0.2em',
            color: P.darkInk,
            opacity: 0.55,
          }}
        >
          384 × 128 GRID
        </div>
        <div style={{position: 'absolute', right: 22, bottom: 14, display: 'flex', alignItems: 'center', gap: 10}}>
          <div style={{display: 'flex'}}>
            {Array.from({length: 36}).map((_, i) => {
              const u = i / 35;
              const c =
                u < 0.55
                  ? mix([26, 52, 52], [76, 122, 118], u / 0.55)
                  : mix([76, 122, 118], [224, 160, 90], (u - 0.55) / 0.45);
              return (
                <div
                  key={i}
                  style={{width: 6, height: 9, background: `rgb(${c.map((v) => Math.round(v)).join(',')})`}}
                />
              );
            })}
          </div>
          <div style={{fontFamily: DISPLAY, fontSize: 13, letterSpacing: '0.16em', color: P.darkInk, opacity: 0.55}}>
            WIND SPEED
          </div>
        </div>
      </div>

      <div
        style={{
          position: 'absolute',
          left: 0,
          top: fieldH,
          width: w,
          height: 1,
          background: P.darkInk,
          opacity: 0.18 * chartOpen,
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: 0,
          top: fieldH,
          width: w,
          height: Math.max(0, chartH),
          overflow: 'hidden',
        }}
      >
      <svg width={w} height={chartFull} viewBox={`0 0 ${w} ${chartFull}`} style={{position: 'absolute', left: 0, top: 0}}>
        {[0, 1, 2].map((k) => (
          <g key={k}>
            <line
              x1={padL}
              y1={py(k)}
              x2={w - padR}
              y2={py(k)}
              stroke={P.darkInk}
              strokeOpacity={k === 1 ? 0.28 : 0.1}
              strokeWidth={1}
              strokeDasharray={k === 1 ? '6 6' : undefined}
            />
            <text
              x={padL - 12}
              y={py(k) + 5}
              textAnchor="end"
              fontFamily={DISPLAY}
              fontSize={14}
              fill={P.darkInk}
              opacity={0.5}
              letterSpacing="0.08em"
            >
              {k}×
            </text>
          </g>
        ))}
        {cq > 0 && <rect x={crestX} y={18} width={cw * 0.3} height={chartFull - 64} fill={P.cinnabar} fillOpacity={0.1 * cq} />}
        <line x1={crestX} y1={18} x2={crestX} y2={chartFull - 46} stroke={P.darkInk} strokeOpacity={0.3 * cq} strokeDasharray="4 6" />
        <path d={curve} fill="none" stroke={P.darkInk} strokeWidth={2.2} strokeLinejoin="round" strokeLinecap="round" />
        {cq > 0.9 && (
          <>
            <text x={crestX} y={26} textAnchor="middle" fontFamily={DISPLAY} fontSize={15} fill={P.warm} letterSpacing="0.16em">
              CREST {DATA.ratios.crest.toFixed(1)}×
            </text>
            <text
              x={crestX + cw * 0.24}
              y={py(DATA.ratios.lee) - 12}
              fontFamily={DISPLAY}
              fontSize={15}
              fill={P.warm}
              letterSpacing="0.16em"
            >
              LEE {DATA.ratios.lee.toFixed(1)}×
            </text>
          </>
        )}
        <text x={padL} y={chartFull - 16} fontFamily={DISPLAY} fontSize={13} fill={P.darkInk} opacity={0.45 * cq} letterSpacing="0.12em">
          WIND SPEED 1 M ABOVE GROUND · NORMALISED TO OPEN GROUND
        </text>
      </svg>
      </div>
    </div>
  );
};

export const panelHeight = (w = 912) => (w * DATA.img.h) / DATA.img.w + 233;
