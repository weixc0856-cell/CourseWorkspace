import React from 'react';
import * as THREE from 'three';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {World} from '../carflow/Scene';
import {C, DISPLAY, FONT, ease, win} from './theme';

export const CarScene: React.FC = () => {
  const t = useCurrentFrame() / 30;
  const title = ease(t / 0.8);
  const path = Math.min(ease((t - 2) / 0.7), 1 - ease((t - 11) / 0.7));
  const air = ease((t - 21) / 0.8);
  const roll = ease((t - 22) / 0.8);
  const ratio = ease((t - 23.5) / 0.8);
  const cap1 = win(t, 4.2, 11.8, 0.6);
  const cap2 = win(t, 11.8, 20.2, 0.6);

  return (
    <AbsoluteFill style={{background: '#05070A'}}>
      <ThreeCanvas
        width={1920}
        height={1080}
        dpr={1}
        shadows
        camera={{fov: 36, position: [6.8, 2.9, 7.8], near: 0.1, far: 200}}
        gl={{antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.08}}
      >
        <World t={t} />
      </ThreeCanvas>

      <div style={{position: 'absolute', left: 84, top: 66, opacity: title, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em', fontFamily: FONT}}>
        T1-01 · 02 / THE BILL
      </div>
      <div style={{position: 'absolute', left: 84, top: 104, width: 1100, opacity: title, transform: `translateY(${(1 - title) * 12}px)`, fontFamily: DISPLAY, fontSize: 44, fontWeight: 600, letterSpacing: '-0.025em', color: C.paper, textShadow: '0 2px 20px rgba(0,0,0,0.8)'}}>
        At 120 km/h, where does the energy go?
      </div>

      <div style={{position: 'absolute', left: 84, bottom: 70, opacity: path, color: 'rgba(244,241,234,0.58)', fontSize: 20, letterSpacing: '0.12em', fontFamily: FONT}}>
        FRONT → ROOF → UNDERBODY → WHEELS → WAKE
      </div>

      <div data-subtitle="cap1" style={{position: 'absolute', left: 84, top: 196, width: 820, opacity: cap1, color: 'rgba(244,241,234,0.82)', fontSize: 25, lineHeight: 1.45, fontFamily: FONT, textShadow: '0 2px 16px rgba(0,0,0,0.9)'}}>
        Over the roof, the air speeds up. Pressure falls.
      </div>
      <div data-subtitle="cap2" style={{position: 'absolute', left: 84, top: 196, width: 820, opacity: cap2, color: 'rgba(244,241,234,0.82)', fontSize: 25, lineHeight: 1.45, fontFamily: FONT, textShadow: '0 2px 16px rgba(0,0,0,0.9)'}}>
        Behind the car, the flow separates. Low pressure, drag.
      </div>

      <div style={{position: 'absolute', left: 96, top: 780, opacity: air, transform: `translateY(${(1 - air) * 12}px)`, fontFamily: FONT, color: C.paper, textShadow: '0 3px 24px rgba(0,0,0,0.95)'}}>
        <div style={{fontSize: 12, letterSpacing: '0.32em', color: 'rgba(244,241,234,0.55)'}}>AIR</div>
        <div style={{marginTop: 8, fontSize: 58, lineHeight: 1, fontWeight: 300, letterSpacing: '-0.04em', color: C.orange}}>
          13.8 <span style={{fontSize: 22, color: 'rgba(244,241,234,0.7)'}}>kW</span>
        </div>
      </div>

      <div style={{position: 'absolute', right: 96, top: 780, opacity: roll, transform: `translateY(${(1 - roll) * 12}px)`, textAlign: 'right', fontFamily: FONT, color: C.paper, textShadow: '0 3px 24px rgba(0,0,0,0.95)'}}>
        <div style={{fontSize: 12, letterSpacing: '0.32em', color: 'rgba(244,241,234,0.55)'}}>ROLLING</div>
        <div style={{marginTop: 8, fontSize: 58, lineHeight: 1, fontWeight: 300, letterSpacing: '-0.04em', color: '#C9D2DB'}}>
          4.2 <span style={{fontSize: 22, color: 'rgba(244,241,234,0.7)'}}>kW</span>
        </div>
      </div>

      <div style={{position: 'absolute', right: 96, top: 96, opacity: ratio, transform: `translateY(${(1 - ratio) * 12}px)`, textAlign: 'right', fontFamily: DISPLAY, color: C.orange, textShadow: '0 2px 18px rgba(0,0,0,0.8)'}}>
        <div style={{fontSize: 92, fontWeight: 600, lineHeight: 0.9, letterSpacing: '-0.05em'}}>3.3<span style={{fontSize: 46}}>×</span></div>
        <div style={{fontSize: 13, letterSpacing: '0.24em', color: 'rgba(244,241,234,0.55)', marginTop: 8}}>AIR / ROLLING</div>
      </div>
    </AbsoluteFill>
  );
};
