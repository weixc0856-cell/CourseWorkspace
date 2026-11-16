import React from 'react';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {SceneFrame} from '../chapter/SceneFrame';
import {C, DISPLAY, FONT, ease} from '../chapter/theme';

// B3 preview: the coefficients in cD are not decoration. The denominator is
// lit term by term so the sentence "shape sets the coefficient, area
// multiplies it" has something to land on.
export const DerivationCard: React.FC<{duration?: number}> = ({duration = 5}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  const appear = ease(t / 0.7);
  const lit = (start: number) => ease((t - start) / 0.5);
  const half = lit(0.7);
  const rho = lit(1.4);
  const area = lit(2.1);
  const speed = lit(2.9);
  const settle = ease((t - 4.0) / 0.6);
  const termColor = (term: string) => {
    if (term === '½' && half > 0.2) return C.orange;
    if (term === 'ρ' && rho > 0.2) return C.orange;
    if (term === 'A' && area > 0.2) return C.orange;
    if ((term === 'v' || term === '²') && speed > 0.2) return C.orange;
    return C.paper;
  };
  const label = (text: string, opacity: number, left: number) => (
    <div
      style={{
        position: 'absolute',
        left,
        top: 610,
        opacity,
        color: 'rgba(244,241,234,0.75)',
        fontSize: 22,
        letterSpacing: '0.16em',
      }}
    >
      {text}
    </div>
  );
  return (
    <SceneFrame
      style={{
        background:
          'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)',
        fontFamily: FONT,
      }}
    >
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        T1-01 · 03 / THE DERIVATION
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, fontFamily: DISPLAY, fontSize: 52, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper, opacity: appear}}>
        The coefficient, defined
      </div>

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 400,
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'center',
          gap: 22,
          fontFamily: 'STIX Two Math, Cambria Math, Georgia, serif',
          fontSize: 148,
          color: C.paper,
          opacity: appear,
          fontStyle: 'italic',
        }}
      >
        <span style={{fontStyle: 'normal', color: settle > 0.2 ? C.orange : C.paper}}>c</span>
        <span style={{fontSize: 64, marginLeft: -6, position: 'relative', top: 26, fontStyle: 'normal'}}>D</span>
        <span style={{fontStyle: 'normal'}}>=</span>
        <span>F</span>
        <span style={{fontStyle: 'normal'}}>/</span>
        <span style={{fontStyle: 'normal'}}>(</span>
        <span style={{color: termColor('½')}}>½</span>
        <span style={{color: termColor('ρ')}}>ρ</span>
        <span style={{color: termColor('A')}}>A</span>
        <span style={{color: termColor('v')}}>v</span>
        <span style={{fontStyle: 'normal', color: termColor('v')}}>²</span>
        <span style={{fontStyle: 'normal'}}>)</span>
      </div>

      {label('cD = shape', settle * 0.9, 1260)}
      {label('½ ρ: air density', half * 0.85, 330)}
      {label('A: frontal area', area * 0.85, 640)}
      {label('v²: speed squared', speed * 0.85, 950)}

      <div
        style={{
          position: 'absolute',
          left: 96,
          right: 96,
          top: 760,
          textAlign: 'center',
          opacity: settle,
          color: C.paper,
          fontSize: 30,
          letterSpacing: '-0.01em',
        }}
      >
        shape sets the coefficient · frontal area multiplies it
      </div>

      <div style={{position: 'absolute', left: 96, right: 96, bottom: 130, display: 'flex', justifyContent: 'space-between', color: 'rgba(244,241,234,0.38)', fontSize: 15, letterSpacing: '0.12em'}}>
        <span>SCHEMATIC · DRAG COEFFICIENT DEFINITION</span>
        <span>WHY A CAR NEEDS AERODYNAMICS</span>
      </div>
    </SceneFrame>
  );
};
