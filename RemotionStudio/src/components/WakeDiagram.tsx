import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT, ease} from '../chapter/theme';

// B2 preview: the drag source is pressure, and the pressure work happens at
// the rear. The rear low-pressure zone pulls back; the wake trails it.
const CAR = 'M 470 600 L 470 520 Q 470 470 530 462 L 700 452 Q 760 450 790 500 L 840 545 L 900 555 L 900 600 Z';

export const WakeDiagram: React.FC<{duration?: number}> = ({duration = 5}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const appear = ease(t / 0.8);
  const pressure = ease((t - 0.8) / 0.8);
  const wake = ease((t - 1.6) / 0.8);

  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        T1-01 · 02 / WHERE DRAG LIVES
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, fontFamily: DISPLAY, fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper, opacity: appear}}>
        Pressure, not paint
      </div>

      <svg width={1728} height={370} viewBox="300 380 1400 300" style={{position: 'absolute', left: 96, top: 300, opacity: appear}}>
        {/* car */}
        <path d={CAR} fill="rgba(244,241,234,0.92)" stroke={C.ink} strokeWidth={3} />
        <circle cx={540} cy={600} r={30} fill={C.ink} stroke={C.muted} strokeWidth={3} />
        <circle cx={820} cy={600} r={30} fill={C.ink} stroke={C.muted} strokeWidth={3} />

        {/* rear low-pressure zone: contours only behind the rear edge */}
        <defs>
          <clipPath id="behind-rear">
            <rect x={905} y={380} width={760} height={300} />
          </clipPath>
        </defs>
        <g clipPath="url(#behind-rear)">
        {[0, 1, 2, 3].map((ring) => {
          const radius = 60 + ring * 58;
          const opacity = pressure * (0.9 - ring * 0.18);
          const pulse = 1 + 0.04 * Math.sin((t * 3.2 + ring * 0.7) * Math.PI);
          return (
            <ellipse
              key={ring}
              cx={930}
              cy={560}
              rx={radius * pulse}
              ry={radius * 0.72 * pulse}
              fill="none"
              stroke={C.orange}
              strokeWidth={2}
              strokeDasharray="8 10"
              opacity={opacity}
            />
          );
        })}
        </g>
        <line x1={1016} y1={482} x2={976} y2={536} stroke={C.orange} strokeWidth={2} opacity={pressure} />
        <text x={1026} y={470} fill={C.orange} fontSize={22} opacity={pressure}>
          low pressure
        </text>
        <text x={930} y={500} fill="rgba(244,241,234,0.6)" fontSize={17} opacity={pressure}>
          pulls the car backwards
        </text>

        {/* wake: three rows of parcels drifting and spreading */}
        {wake > 0
          ? [0, 1, 2].map((row) =>
              Array.from({length: 9}).map((_, index) => {
                const phase = (t * 0.55 + index / 9 + row * 0.12) % 1;
                const x = 930 + phase * 680;
                const spread = (row - 1) * (24 + phase * 90);
                const y = 560 + spread + Math.sin((phase * 3 + row) * Math.PI) * 10;
                return (
                  <g key={`${row}-${index}`} opacity={wake * (1 - phase * 0.75)}>
                    <circle cx={x} cy={y} r={7} fill={C.orangeSoft} />
                    <line x1={x + 9} y1={y} x2={x + 30} y2={y} stroke={C.orange} strokeWidth={2} />
                  </g>
                );
              }),
            )
          : null}
        <text x={1180} y={420} fill="rgba(244,241,234,0.6)" fontSize={17} opacity={wake}>
          wake
        </text>

        {/* relative airflow (left -> right) and car motion (right -> left) */}
        <g opacity={pressure}>
          <line x1={320} y1={400} x2={560} y2={400} stroke={C.paper} strokeWidth={3} />
          <path d="M 560 400 l -14 -7 l 0 14 z" fill={C.paper} />
          <text x={320} y={386} fill="rgba(244,241,234,0.7)" fontSize={18}>relative airflow</text>
          <line x1={700} y1={672} x2={470} y2={672} stroke="rgba(244,241,234,0.55)" strokeWidth={3} strokeDasharray="12 10" />
          <path d="M 470 672 l 14 -7 l 0 14 z" fill="rgba(244,241,234,0.55)" />
          <text x={700} y={668} fill="rgba(244,241,234,0.55)" fontSize={17}>car motion</text>
        </g>

        {/* friction along the lower body edge */}
        <path d="M 570 598 L 860 598" stroke={C.orangeSoft} strokeWidth={12} opacity={0.8 * pressure} />
        <text x={600} y={626} fill="rgba(244,241,234,0.55)" fontSize={16} opacity={pressure}>friction on the lower body</text>

        {/* front stagnation label */}
        <line x1={470} y1={520} x2={440} y2={464} stroke={C.muted} strokeWidth={2} opacity={pressure} />
        <text x={330} y={452} fill="rgba(244,241,234,0.7)" fontSize={19} opacity={pressure}>
          pressure builds here
        </text>

        {/* friction layer */}
        <path d="M 500 462 L 780 452" stroke={C.orangeSoft} strokeWidth={14} opacity={0.9 * pressure} />
        <text x={700} y={416} fill="rgba(244,241,234,0.5)" fontSize={16} opacity={pressure}>
          friction: thin layer
        </text>
      </svg>

      {/* Quantitative split: pressure dominates, friction is the remainder. */}
      <div style={{position: 'absolute', left: 96, top: 716, width: 1500, opacity: pressure}}>
        <div style={{display: 'flex', justifyContent: 'space-between', marginBottom: 10, color: 'rgba(244,241,234,0.62)', fontSize: 18, letterSpacing: '0.14em'}}>
          <span>PRESSURE &gt; 80%</span>
          <span>COOLING ≈ 10%</span>
          <span>FRICTION &lt; 10%</span>
        </div>
        <div style={{display: 'flex', height: 26}}>
          <div style={{width: '80%', background: C.orange}} />
          <div style={{width: '10%', background: 'rgba(244,241,234,0.72)'}} />
          <div style={{width: '10%', background: 'rgba(244,241,234,0.28)'}} />
        </div>
        <div style={{marginTop: 12, color: 'rgba(244,241,234,0.45)', fontSize: 16, letterSpacing: '0.08em'}}>
          share of total drag at highway speed
        </div>
      </div>

      <div style={{position: 'absolute', left: 96, right: 96, bottom: 130, display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.38)', fontSize: 15, letterSpacing: '0.12em'}}>
        <span>SCHEMATIC · PRESSURE DRAG AT THE REAR</span>
        <span>{"engineered, not photographed"}</span>
      </div>
    </SceneFrame>
  );
};
