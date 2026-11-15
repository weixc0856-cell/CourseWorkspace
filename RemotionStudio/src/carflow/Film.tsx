import React from 'react';
import * as THREE from 'three';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {World} from './Scene';

const ease = (t: number, a: number, b: number) => {
  const p = Math.max(0, Math.min(1, (t - a) / (b - a)));
  return p * p * (3 - 2 * p);
};

const Label: React.FC<{
  t: number;
  a: number;
  b: number;
  x: number;
  y: number;
  align?: 'left' | 'right';
  kicker: string;
  value: string;
  unit?: string;
  color: string;
}> = ({t, a, b, x, y, align = 'left', kicker, value, unit, color}) => {
  const inP = ease(t, a, a + 0.7);
  const outP = 1 - ease(t, b - 0.6, b);
  const p = Math.min(inP, outP);
  if (p <= 0) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        opacity: p,
        transform: `translateY(${(1 - inP) * 14}px)`,
        textAlign: align,
        color: '#F4F1EA',
        textShadow: '0 3px 26px rgba(0,0,0,0.95), 0 1px 3px rgba(0,0,0,0.9)',
        fontFamily: '"Segoe UI", Arial, sans-serif',
        pointerEvents: 'none',
      }}
    >
      <div style={{fontSize: 13, letterSpacing: '0.32em', color: 'rgba(244,241,234,0.55)'}}>{kicker}</div>
      <div style={{marginTop: 8, fontSize: 64, lineHeight: 1, fontWeight: 300, letterSpacing: '-0.04em', color}}>
        {value}
        {unit ? <span style={{fontSize: 22, marginLeft: 8, letterSpacing: '0.04em', color: 'rgba(244,241,234,0.7)'}}>{unit}</span> : null}
      </div>
    </div>
  );
};

const Labels: React.FC<{t: number}> = ({t}) => {
  const wake = Math.min(ease(t, 14.5, 16), 1 - ease(t, 20.5, 21.8));
  const foot = ease(t, 24, 25.5);
  return (
    <>
      <div
        style={{
          position: 'absolute',
          left: 84,
          top: 66,
          opacity: Math.min(ease(t, 0.2, 1.2), 1 - ease(t, 3.2, 4.2)),
          color: 'rgba(244,241,234,0.5)',
          fontSize: 12,
          letterSpacing: '0.34em',
          fontFamily: '"Segoe UI", Arial, sans-serif',
        }}
      >
        CAR FLOW / 30 S TEST / SCHEMATIC
      </div>

      <div
        style={{
          position: 'absolute',
          left: 110,
          top: 250,
          opacity: wake,
          transform: `translateY(${(1 - wake) * 10}px)`,
          textAlign: 'left',
          color: 'rgba(244,241,234,0.8)',
          fontFamily: '"Segoe UI", Arial, sans-serif',
        }}
      >
        <div style={{fontSize: 13, letterSpacing: '0.32em', color: 'rgba(111,211,232,0.9)'}}>SEPARATION</div>
        <div style={{marginTop: 8, fontSize: 36, fontWeight: 300, letterSpacing: '-0.02em'}}>wake / low pressure</div>
      </div>

      <Label t={t} a={21.2} b={30} x={96} y={780} kicker="AIR" value="13.8" unit="kW" color="#E8733B" />
      <Label t={t} a={21.8} b={30} x={1490} y={620} align="right" kicker="ROLLING" value="4.2" unit="kW" color="#C9D2DB" />

      <div
        style={{
          position: 'absolute',
          left: 84,
          bottom: 64,
          opacity: foot,
          color: 'rgba(244,241,234,0.42)',
          fontSize: 12,
          letterSpacing: '0.12em',
          lineHeight: 1.6,
          fontFamily: '"Segoe UI", Arial, sans-serif',
        }}
      >
        SCHEMATIC · model calculation, Table 3.1, 120 km/h
        <br />
        flow field is illustrative, not CFD
      </div>
    </>
  );
};

export const CarFlow: React.FC = () => {
  const frame = useCurrentFrame();
  const t = frame / 30;
  return (
    <AbsoluteFill
      style={{
        background:
          'radial-gradient(120% 90% at 50% 42%, #151C26 0%, #0B0F15 48%, #05070A 100%)',
      }}
    >
      <ThreeCanvas
        width={1920}
        height={1080}
        dpr={1}
        shadows
        camera={{fov: 36, position: [6, 2.6, 7], near: 0.1, far: 200}}
        gl={{
          antialias: true,
          alpha: true,
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.08,
        }}
      >
        <World t={t} />
      </ThreeCanvas>
      <Labels t={t} />
    </AbsoluteFill>
  );
};
