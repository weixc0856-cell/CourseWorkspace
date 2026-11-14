import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {C, DISPLAY, FPS, H, SANS, W, clamp01, easeOut, lerp, seg, smooth} from './theme';

const KAI = '"STKaiti", "KaiTi", serif';

const range = (n: number) => Array.from({length: n}, (_, i) => i);

// ---------------------------------------------------------------- sky
const Sky: React.FC<{t: number}> = ({t}) => {
  const rise = easeOut(seg(t, 0.2, 4.5));
  return (
    <>
      <AbsoluteFill
        style={{
          background: `linear-gradient(to bottom, ${C.skyTop} 0%, ${C.skyMid} 38%, ${C.skyLow} 62%, #3a5a56 74%, #24403f 84%, #12262c 100%)`,
        }}
      />
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute'}}>
        <defs>
          <radialGradient id="halo">
            <stop offset="0%" stopColor={C.sunHalo} stopOpacity={0.55} />
            <stop offset="55%" stopColor={C.sunHalo} stopOpacity={0.16} />
            <stop offset="100%" stopColor={C.sunHalo} stopOpacity={0} />
          </radialGradient>
        </defs>
        <circle cx={706} cy={lerp(980, 930, rise)} r={420} fill="url(#halo)" />
        <circle cx={706} cy={lerp(980, 930, rise)} r={132} fill={C.sun} />
        <circle cx={706} cy={lerp(980, 930, rise)} r={132} fill={C.sunHalo} opacity={0.25} />
      </svg>
    </>
  );
};

// ---------------------------------------------------------------- mountains
const FarRange: React.FC<{t: number; parallax: number}> = ({t, parallax}) => {
  const p = easeOut(seg(t, 0.6, 5));
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute', transform: `translateX(${-parallax * 18}px)`}}>
      <path
        d="M-80,1210 L60,1090 L150,1140 L250,1010 L330,1080 L430,975 L520,1060 L640,1005 L760,1105 L880,1030 L1000,1120 L1160,1060 L1160,1400 L-80,1400 Z"
        fill={C.far}
        opacity={0.9 * p}
      />
      <path
        d="M-80,1260 L90,1150 L210,1210 L320,1115 L430,1190 L560,1105 L690,1200 L820,1130 L950,1215 L1160,1150 L1160,1400 L-80,1400 Z"
        fill={C.mid}
        opacity={0.95 * p}
      />
    </svg>
  );
};

const MidRidge: React.FC<{t: number; parallax: number}> = ({t, parallax}) => {
  const p = easeOut(seg(t, 1.0, 5.5));
  const pines = [
    [150, 1210, 1],
    [215, 1195, 0.8],
    [700, 1180, 0.9],
    [770, 1200, 1.1],
    [880, 1190, 0.75],
  ] as const;
  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{position: 'absolute', transform: `translateX(${-parallax * 34}px)`}}
    >
      <path
        d="M-80,1300 C120,1235 260,1275 380,1240 C520,1200 610,1235 700,1215 C820,1190 950,1235 1160,1205 L1160,1500 L-80,1500 Z"
        fill={C.near}
        opacity={p}
      />
      {pines.map(([x, y, s], i) => (
        <g key={i} opacity={p}>
          <line x1={x} y1={y} x2={x} y2={y - 52 * s} stroke={C.ink} strokeWidth={3} />
          <path
            d={`M${x - 20 * s},${y - 22 * s} L${x},${y - 60 * s} L${x + 20 * s},${y - 22 * s} Z`}
            fill={C.ink}
            opacity={0.92}
          />
          <path
            d={`M${x - 14 * s},${y - 40 * s} L${x},${y - 70 * s} L${x + 14 * s},${y - 40 * s} Z`}
            fill={C.ink}
            opacity={0.92}
          />
        </g>
      ))}
    </svg>
  );
};

// ---------------------------------------------------------------- river
const River: React.FC<{t: number}> = ({t}) => {
  const p = easeOut(seg(t, 0.8, 4));
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute'}}>
      <path d="M-40,1240 L1120,1215 L1120,1600 L-40,1620 Z" fill={C.river} opacity={p} />
      {range(9).map((i) => {
        const y = 1270 + i * 36;
        const speed = 26 + i * 9;
        const off = ((t * speed + i * 120) % 1400) - 200;
        const len = 180 + (i % 4) * 90;
        return (
          <rect
            key={i}
            x={off}
            y={y}
            width={len}
            height={i % 3 === 0 ? 3 : 2}
            fill={C.riverHi}
            opacity={(0.12 + (i % 4) * 0.05) * p}
          />
        );
      })}
      <path d="M-40,1240 L1120,1215 L1120,1242 L-40,1268 Z" fill={C.riverHi} opacity={0.35 * p} />
    </svg>
  );
};

// ---------------------------------------------------------------- clouds
const cloudPath = (x: number, y: number, s: number) =>
  `M${x - 90 * s},${y} c0,-22 ${18 * s},-38 ${40 * s},-34 c6,-26 ${34 * s},-40 ${58 * s},-28 c16,-22 ${54 * s},-18 ${60 * s},6 c24,-4 ${40 * s},10 ${40 * s},26 c0,16 ${-16 * s},22 ${-30 * s},22 L${x - 90 * s},${y} Z`;

const Clouds: React.FC<{t: number; depth: number; y: number; s: number; speed: number; opacity: number}> = ({
  t,
  depth,
  y,
  s,
  speed,
  opacity,
}) => {
  const x = ((t * speed) % (W + 400)) - 200;
  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      style={{position: 'absolute', transform: `translateX(${-depth * 22}px)`}}
    >
      <path d={cloudPath(x, y, s)} fill={C.paper} opacity={opacity} />
      <path d={cloudPath(x + 520, y + 70, s * 0.66)} fill={C.paper} opacity={opacity * 0.7} />
      <path d={cloudPath(x - 420, y + 150, s * 0.5)} fill={C.paper} opacity={opacity * 0.45} />
    </svg>
  );
};

// ---------------------------------------------------------------- figure
const Figure: React.FC<{t: number}> = ({t}) => {
  const sway = Math.sin(t * 1.05) * 0.8 + Math.sin(t * 2.2 + 0.6) * 0.3;
  const flutter = (k: number) => Math.sin(t * 2.0 + k * 0.9) * 11 + Math.sin(t * 3.6 + k) * 4;
  const hem = (k: number) => Math.sin(t * 1.6 + k * 1.3) * 4;
  const baseX = 340;
  const baseY = 1368;
  return (
    <g transform={`translate(${baseX} ${baseY}) rotate(${sway})`}>
      {/* neck */}
      <path d="M-2,-232 L18,-232 L20,-214 L-4,-214 Z" fill={C.ink} />
      {/* robe */}
      <path
        d={`M-30,-216
            C-40,-186 -50,-140 -58,-78
            C-62,-46 -74,${-12 + hem(0)} -92,${-4 + hem(1)}
            C-40,${8 + hem(2)} 26,${10 + hem(3)} 70,${-2 + hem(2)}
            C60,-58 50,-140 38,-190
            C22,-206 6,-214 -30,-216 Z`}
        fill={C.ink}
      />
      {/* windward bell sleeve */}
      <path
        d="M-30,-216 C-66,-212 -92,-176 -96,-128 C-74,-118 -48,-128 -34,-150 Z"
        fill={C.ink}
      />
      {/* straw hat (斗笠) */}
      <path d="M-46,-250 C-20,-300 40,-300 66,-250 C40,-262 -18,-262 -46,-250 Z" fill={C.ink} />
      <path d="M-46,-250 C-20,-240 40,-240 66,-250 C40,-244 -18,-244 -46,-250 Z" fill={C.near} opacity={0.9} />
      {/* face profile under the brim */}
      <path d="M2,-248 C2,-232 10,-222 22,-220 C30,-220 34,-228 34,-236 L34,-248 Z" fill={C.ink} />
      {/* rim light on the windward silhouette */}
      <path
        d={`M38,-190 C50,-140 60,-58 70,-2`}
        fill="none"
        stroke={C.paper}
        strokeWidth={2.2}
        strokeOpacity={0.22}
      />
      <path d="M66,-250 C40,-262 -18,-262 -46,-250" fill="none" stroke={C.paper} strokeWidth={2} strokeOpacity={0.18} />
      {/* sash ribbons */}
      {range(3).map((i) => {
        const f = flutter(i);
        const len = 96 + i * 26;
        return (
          <path
            key={i}
            d={`M${12},${-120 + i * 14} C${56},${-126 + i * 14 + f} ${96},${-114 + i * 16 - f} ${len + 40},${-102 + i * 18 + f * 0.6}`}
            fill="none"
            stroke={C.sun}
            strokeWidth={6 - i}
            strokeOpacity={0.9 - i * 0.16}
            strokeLinecap="round"
          />
        );
      })}
    </g>
  );
};

const Cliff: React.FC<{t: number}> = ({t}) => {
  void t;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute'}}>
      <path
        d="M-40,1660 L-40,1430 C60,1396 150,1380 230,1370 L300,1364 C360,1358 420,1362 470,1374
           C430,1392 380,1400 330,1404 C300,1420 280,1460 268,1520 C250,1580 200,1616 130,1636 Z"
        fill={C.cliff}
      />
      <path
        d="M-40,1446 C60,1410 150,1396 232,1386 L300,1378 C356,1372 410,1376 456,1388
           C420,1392 380,1398 336,1400 C300,1414 280,1450 270,1500 L236,1490 C180,1480 90,1486 -40,1520 Z"
        fill={C.near}
        opacity={0.55}
      />
      <Figure t={t} />
    </svg>
  );
};

// ---------------------------------------------------------------- wind
const Wind: React.FC<{t: number; opacity: number}> = ({t, opacity}) => (
  <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{position: 'absolute'}}>
    {range(14).map((i) => {
      const y = 620 + ((i * 83) % 640);
      const speed = 150 + (i % 5) * 55;
      const x = ((t * speed + i * 240) % (W + 500)) - 250;
      const len = 90 + (i % 4) * 70;
      const curve = 8 + (i % 3) * 10;
      return (
        <path
          key={i}
          d={`M${x},${y} C${x + len * 0.35},${y - curve} ${x + len * 0.7},${y + curve} ${x + len},${y}`}
          fill="none"
          stroke={C.paper}
          strokeWidth={i % 3 === 0 ? 2.4 : 1.5}
          strokeOpacity={(0.1 + (i % 4) * 0.045) * opacity}
          strokeLinecap="round"
        />
      );
    })}
    {range(26).map((i) => {
      const speed = 170 + (i % 6) * 40;
      const x = ((t * speed + i * 137) % (W + 300)) - 150;
      const y = 700 + ((i * 47) % 520) + Math.sin(t * 1.6 + i) * 14;
      return <circle key={`p${i}`} cx={x} cy={y} r={1.4 + (i % 3) * 0.7} fill={C.paper} opacity={0.18 * opacity} />;
    })}
  </svg>
);

// ---------------------------------------------------------------- type
const Type: React.FC<{t: number}> = ({t}) => {
  const words = ['THE', 'WIND', 'PICKS', 'THE', 'SITE.'];
  return (
    <div style={{position: 'absolute', left: 84, top: 300, right: 84}}>
      <div style={{display: 'flex', flexWrap: 'wrap', gap: '0 22px'}}>
        {words.map((w, i) => {
          const p = easeOut(seg(t, 3.4 + i * 0.16, 3.9 + i * 0.16));
          const accent = w === 'SITE.';
          return (
            <div key={i} style={{overflow: 'hidden'}}>
              <div
                style={{
                  fontFamily: DISPLAY,
                  fontWeight: 900,
                  fontSize: 96,
                  lineHeight: 0.98,
                  letterSpacing: accent ? '-0.01em' : '-0.03em',
                  color: accent ? C.gold : C.paper,
                  transform: `translateY(${(1 - p) * 108}%)`,
                  opacity: p > 0 ? 1 : 0,
                }}
              >
                {w}
              </div>
            </div>
          );
        })}
      </div>
      <div style={{marginTop: 26, height: 2, width: 180 * easeOut(seg(t, 6.0, 6.8)), background: C.gold, opacity: 0.8}} />
      <div
        style={{
          marginTop: 22,
          fontFamily: SANS,
          fontSize: 42,
          color: C.paper,
          opacity: easeOut(seg(t, 6.3, 7.1)),
          transform: `translateY(${(1 - easeOut(seg(t, 6.3, 7.1))) * 8}px)`,
        }}
      >
        风先到，人选地。
      </div>
    </div>
  );
};

// ---------------------------------------------------------------- film
export const GuofengSample: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / FPS;
  const cam = 1 + 0.055 * smooth(t / 10);
  const fade = easeOut(seg(t, 0, 0.9));

  return (
    <AbsoluteFill style={{backgroundColor: C.ink}}>
      <AbsoluteFill style={{transform: `scale(${cam})`, transformOrigin: '52% 62%'}}>
        <Sky t={t} />
        <FarRange t={t} parallax={0.4} />
        <Clouds t={t} depth={0.7} y={520} s={0.95} speed={9} opacity={0.14} />
        <MidRidge t={t} parallax={0.8} />
        <River t={t} />
        <Clouds t={t} depth={1.0} y={790} s={0.72} speed={15} opacity={0.16} />
        <Cliff t={t} />
        <Wind t={t} opacity={1} />
      </AbsoluteFill>

      <Type t={t} />

      <AbsoluteFill
        style={{
          background: 'radial-gradient(90% 60% at 50% 46%, rgba(0,0,0,0) 45%, rgba(3,10,12,0.55) 100%)',
        }}
      />
      <Img
        src={staticFile('fengshui/paper.png')}
        style={{position: 'absolute', inset: 0, width: W, height: H, opacity: 0.05, objectFit: 'cover'}}
      />
      <AbsoluteFill style={{backgroundColor: C.ink, opacity: 1 - fade, pointerEvents: 'none'}} />
      <AbsoluteFill style={{backgroundColor: C.ink, opacity: clamp01((t - 9.4) / 0.6) * 0.9, pointerEvents: 'none'}} />
    </AbsoluteFill>
  );
};
