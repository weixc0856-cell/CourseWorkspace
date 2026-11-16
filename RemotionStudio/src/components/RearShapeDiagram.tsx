import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT, ease} from '../chapter/theme';

// B7 preview: the rear decides. Three classical backs, their wakes, and the
// packaging each one buys or loses.
const Backs: React.FC<{x: number; kind: 'square' | 'fast' | 'notch'; opacity: number; wake: number}> = ({
  x, kind, opacity, wake,
}) => {
  const body =
    kind === 'square'
      ? 'M 0 470 L 0 300 L 40 292 L 250 292 L 300 300 L 300 470 Z'
      : kind === 'fast'
        ? 'M 0 470 L 0 330 Q 30 300 80 292 L 190 280 Q 260 285 300 470 Z'
        : 'M 0 470 L 0 330 Q 30 300 80 292 L 210 290 L 260 300 L 300 330 L 300 470 Z';
  return (
    <g transform={`translate(${x}, 0)`} opacity={opacity}>
      <path d={body} fill="rgba(244,241,234,0.9)" stroke={C.ink} strokeWidth={3} />
      <circle cx={40} cy={470} r={26} fill={C.ink} stroke={C.muted} strokeWidth={3} />
      <circle cx={240} cy={470} r={26} fill={C.ink} stroke={C.muted} strokeWidth={3} />
      {[0, 1, 2].map((ring) => (
        <ellipse
          key={ring}
          cx={330}
          cy={380}
          rx={(wake + ring * 24) * (0.8 + 0.2 * Math.sin(ring))}
          ry={(wake + ring * 24) * 0.55}
          fill="none"
          stroke={C.orange}
          strokeWidth={2}
          strokeDasharray="7 9"
          opacity={0.75 - ring * 0.18}
        />
      ))}
    </g>
  );
};

export const RearShapeDiagram: React.FC<{duration?: number}> = ({duration = 5}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const appear = ease(t / 0.7);
  const wake = 42 + 8 * Math.sin(t * 2.2);
  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        T1-01 · 07 / WHY NOT A TEARDROP
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, fontFamily: DISPLAY, fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper, opacity: appear}}>
        The rear decides
      </div>

      <svg width={1728} height={346} viewBox="80 250 1600 320" style={{position: 'absolute', left: 96, top: 300, opacity: appear}}>
        <Backs x={120} kind="square" opacity={appear} wake={wake * 1.25} />
        <Backs x={700} kind="notch" opacity={appear} wake={wake * 0.9} />
        <Backs x={1280} kind="fast" opacity={appear} wake={wake * 0.75} />
        <text x={120} y={515} fill="rgba(244,241,234,0.7)" fontSize={22}>SQUAREBACK · largest wake · most boot</text>
        <text x={700} y={515} fill="rgba(244,241,234,0.7)" fontSize={22}>NOTCHBACK · middle on both</text>
        <text x={1280} y={515} fill={C.orange} fontSize={22}>FASTBACK · best recovery · least boot</text>
      </svg>

      <div style={{position: 'absolute', left: 96, top: 716, width: 1500}}>
        <div style={{height: 2, background: 'rgba(244,241,234,0.14)', marginBottom: 16}} />
        <div style={{display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.65)', fontSize: 22}}>
          <span>wake ↓ left to right · boot ↓ left to right</span>
          <span style={{color: C.orange}}>better recovery costs boot space</span>
        </div>
        <div style={{marginTop: 14, color: 'rgba(244,241,234,0.45)', fontSize: 18}}>
          squareback → notchback → fastback: the better the recovery, the smaller the boot
        </div>
      </div>

      <div style={{position: 'absolute', left: 96, right: 96, bottom: 130, display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.38)', fontSize: 15, letterSpacing: '0.12em'}}>
        <span>SCHEMATIC · REAR SHAPES AND WAKES</span>
        <span>RECOVERY VS PACKAGING</span>
      </div>
    </SceneFrame>
  );
};
