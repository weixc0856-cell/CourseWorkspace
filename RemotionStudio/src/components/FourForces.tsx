import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT, ease} from '../chapter/theme';

// B1 preview: four forces push back, and only two can be recovered. The
// recoverable pair is routed to a battery so the sentence has a destination.
const Arrow: React.FC<{x1: number; y1: number; x2: number; y2: number; color: string; opacity: number}> = ({
  x1, y1, x2, y2, color, opacity,
}) => (
  <g opacity={opacity}>
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke={color} strokeWidth={5} />
    <path
      d={`M ${x2} ${y2} l ${x2 > x1 ? -16 : 16} -8 l 0 16 z`}
      fill={color}
    />
  </g>
);

export const FourForces: React.FC<{duration?: number}> = ({duration = 5}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const appear = ease(t / 0.7);
  const recover = ease((t - 2.4) / 0.8);

  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        T1-01 · 01 / THE QUESTION
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, fontFamily: DISPLAY, fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper, opacity: appear}}>
        Four forces push back
      </div>

      <svg width={1728} height={430} viewBox="120 250 1600 400" style={{position: 'absolute', left: 96, top: 300, opacity: appear}}>
        {/* car */}
        <path
          d="M 560 470 L 560 360 Q 560 320 610 314 L 860 300 Q 930 298 965 352 L 1030 410 L 1100 420 L 1100 470 Z"
          fill="rgba(244,241,234,0.92)"
          stroke={C.ink}
          strokeWidth={3}
        />
        <circle cx={640} cy={470} r={34} fill={C.ink} stroke={C.muted} strokeWidth={3} />
        <circle cx={1010} cy={470} r={34} fill={C.ink} stroke={C.muted} strokeWidth={3} />

        {/* rolling + air: not recoverable */}
        <Arrow x1={640} y1={510} x2={640} y2={585} color={C.paper} opacity={appear} />
        <text x={672} y={612} fill={C.paper} fontSize={22}>ROLLING · cannot be recovered</text>
        <Arrow x1={420} y1={390} x2={520} y2={390} color={C.paper} opacity={appear} />
        <text x={250} y={368} fill={C.paper} fontSize={22}>AIR · cannot be recovered</text>
        <g opacity={appear}>
          <line x1={150} y1={300} x2={430} y2={300} stroke={C.paper} strokeWidth={3} />
          <path d="M 430 300 l -14 -7 l 0 14 z" fill={C.paper} />
          <text x={150} y={286} fill="rgba(244,241,234,0.7)" fontSize={18}>relative airflow</text>
          <line x1={900} y1={640} x2={650} y2={640} stroke="rgba(244,241,234,0.55)" strokeWidth={3} strokeDasharray="12 10" />
          <path d="M 650 640 l 14 -7 l 0 14 z" fill="rgba(244,241,234,0.55)" />
          <text x={900} y={636} fill="rgba(244,241,234,0.55)" fontSize={17}>car motion</text>
        </g>

        {/* grade + inertia: recoverable */}
        <Arrow x1={1130} y1={400} x2={1250} y2={400} color={C.orange} opacity={appear} />
        <text x={1150} y={378} fill={C.orange} fontSize={22}>INERTIA</text>
        <line x1={1100} y1={590} x2={1300} y2={530} stroke={C.orange} strokeWidth={5} opacity={appear} />
        <text x={1130} y={620} fill={C.orange} fontSize={22}>GRADE</text>

        {/* battery: the two recoverable arrows route here */}
        <g opacity={recover}>
          <line x1={1250} y1={400} x2={1430} y2={400} stroke={C.orange} strokeWidth={3} strokeDasharray="10 8" />
          <line x1={1300} y1={530} x2={1430} y2={440} stroke={C.orange} strokeWidth={3} strokeDasharray="10 8" />
          <rect x={1430} y={360} width={180} height={110} rx={12} fill="rgba(232,115,59,0.10)" stroke={C.orange} strokeWidth={3} />
          <rect x={1610} y={395} width={16} height={40} fill={C.orange} />
          <text x={1452} y={425} fill={C.orange} fontSize={22}>BATTERY</text>
          <text x={1452} y={452} fill="rgba(244,241,234,0.6)" fontSize={15}>recovered</text>
        </g>
        
      </svg>

      <div style={{position: 'absolute', left: 96, top: 720, width: 1500, opacity: appear}}>
        <div style={{height: 2, background: 'rgba(244,241,234,0.14)', marginBottom: 18}} />
        <div style={{display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.72)', fontSize: 24}}>
          <span>AIR · 13.8 kW at 120 km/h</span>
          <span>ROLLING · 4.2 kW</span>
          <span style={{color: C.orange}}>GRADE + INERTIA · recovered</span>
        </div>
      </div>

      <div style={{position: 'absolute', left: 96, right: 96, bottom: 130, display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.38)', fontSize: 15, letterSpacing: '0.12em'}}>
        <span>SCHEMATIC · FOUR RESISTANCES</span>
        <span>TWO ARE RECOVERABLE</span>
      </div>
    </SceneFrame>
  );
};
