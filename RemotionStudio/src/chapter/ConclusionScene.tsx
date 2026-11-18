import React from 'react';
import {SceneFrame} from './SceneFrame';
import * as THREE from 'three';
import {useSceneTime} from './timing';
import {ThreeCanvas} from '@remotion/three';
import {World} from '../carflow/Scene';
import {C, DISPLAY, FONT, ease} from './theme';

export const ConclusionScene: React.FC<{
  duration?: number;
  car?: 'drivaer' | 'procedural';
}> = ({duration, car = 'drivaer'}) => {
  const t = useSceneTime(duration);
  const worldT = 25.6 + t * 0.085;
  const q = ease(t / 0.8);
  const l1 = ease((t - 3) / 0.7);
  const l2 = ease((t - 8) / 0.7);
  const l3 = ease((t - 13) / 0.7);
  const fuel = ease((t - 19) / 0.8);
  const src = ease((t - 22) / 0.8);

  return (
    <SceneFrame style={{background: '#05070A'}}>
      <ThreeCanvas
        width={1920}
        height={1080}
        dpr={1}
        shadows
        camera={{fov: 36, position: [-9.2, 3.0, 8.2], near: 0.1, far: 200}}
        gl={{antialias: true, alpha: true, toneMapping: THREE.ACESFilmicToneMapping, toneMappingExposure: 1.08}}
      >
        <World t={worldT} car={car} />
      </ThreeCanvas>

      <div style={{position: 'absolute', left: 96, top: 96, opacity: q, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em', fontFamily: FONT}}>
        T1-01 · 05 / WHAT IT MEANS
      </div>
      <div style={{position: 'absolute', left: 96, top: 138, width: 900, opacity: q, transform: `translateY(${(1 - q) * 12}px)`, fontFamily: DISPLAY, fontSize: 56, fontWeight: 600, lineHeight: 1.02, letterSpacing: '-0.035em', color: C.paper, textShadow: '0 3px 24px rgba(0,0,0,0.9)'}}>
        Shape is the energy bill.
      </div>

      <div style={{position: 'absolute', left: 96, top: 300, width: 650, fontFamily: FONT, color: C.paper, textShadow: '0 3px 22px rgba(0,0,0,0.95)'}}>
        <div style={{opacity: l1, transform: `translateY(${(1 - l1) * 12}px)`, display: 'flex', gap: 18, fontSize: 26, lineHeight: 1.45, marginBottom: 22}}>
          <span style={{color: C.orange, fontFamily: DISPLAY, fontWeight: 600}}>01</span>
          <span>Above ~60 km/h, air is the main load.</span>
        </div>
        <div style={{opacity: l2, transform: `translateY(${(1 - l2) * 12}px)`, display: 'flex', gap: 18, fontSize: 26, lineHeight: 1.45, marginBottom: 22}}>
          <span style={{color: C.orange, fontFamily: DISPLAY, fontWeight: 600}}>02</span>
          <span>2× speed: 4× force, 8× power.</span>
        </div>
        <div style={{opacity: l3, transform: `translateY(${(1 - l3) * 12}px)`, display: 'flex', gap: 18, fontSize: 26, lineHeight: 1.45}}>
          <span style={{color: C.orange, fontFamily: DISPLAY, fontWeight: 600}}>03</span>
          <span>Shape sets c<sub>D</sub>; area multiplies it.</span>
        </div>
      </div>

      <div style={{position: 'absolute', left: 96, top: 820, opacity: fuel, transform: `translateY(${(1 - fuel) * 12}px)`, padding: '18px 24px', borderLeft: `4px solid ${C.orange}`, background: 'rgba(232,115,59,0.10)', color: C.paper, fontSize: 26, lineHeight: 1.45, textShadow: '0 2px 14px rgba(0,0,0,0.9)'}}>
        c<sub>D</sub> 0.30 → 0.26: about <b>0.6 l/100 km</b> at a constant 140 km/h.
      </div>

      <div style={{position: 'absolute', left: 96, bottom: 130, opacity: src, color: 'rgba(244,241,234,0.35)', fontSize: 13, letterSpacing: '0.1em'}}>
        SYNTHESIS · Ch. 3 §3.1–3.2.6 · Fig. 3.25, p. 187 · MODEL CALCULATION AT 120 km/h
      </div>
    </SceneFrame>
  );
};
