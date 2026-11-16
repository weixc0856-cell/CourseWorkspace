import React from 'react';
import {SceneFrame} from './SceneFrame';
import { Img, staticFile} from 'remotion';
import {useSceneTime} from './timing';
import {C, DISPLAY, FONT, ease} from './theme';

export type PhotoInsertProps = {
  image?: string;
  eyebrow?: string;
  headline?: React.ReactNode;
  values?: React.ReactNode;
  question?: string;
  punchline?: string;
  leftLabel?: React.ReactNode;
  rightLabel?: React.ReactNode;
  source?: string;
  footer?: string;
  duration?: number;
};

export const PhotoScene: React.FC<PhotoInsertProps> = ({
  image = 'staging/t1-01-why-aerodynamics/car-hero.png',
  eyebrow = 'T1-01 · 01 / THE QUESTION',
  headline = (
    <>
      Same family.
      <br />
      Two shapes.
    </>
  ),
  values = (
    <>
      c<sub>D</sub> <span style={{color: C.orange}}>0.376</span> &nbsp;→&nbsp; <span style={{color: C.orange}}>0.27</span>
    </>
  ),
  question = 'Why does that matter at 120 km/h?',
  punchline = 'At speed, the shape becomes a bill.',
  leftLabel = (
    <>
      W 194 · 1951/52 · c<sub>D</sub> 0.376
    </>
  ),
  rightLabel = (
    <>
      R 231 · c<sub>D</sub> 0.27
    </>
  ),
  source = 'Fig. 1.67, p. 61 · Schuetz (ed.), Aerodynamics of Road Vehicles, 5th ed. · Photos: Daimler AG',
  footer = 'MODEL: SAME FAMILY, TWO GENERATIONS · cD IS NOT A STYLE CHOICE',
  duration,
}) => {
  const t = useSceneTime(duration);
  const panel = ease(t / 1.1);
  const l1 = ease((t - 0.4) / 0.7);
  const l2 = ease((t - 1.6) / 0.7);
  const l3 = ease((t - 5.5) / 0.7);
  const l4 = ease((t - 12.5) / 0.7);
  const src = ease((t - 11) / 0.7);

  return (
    <SceneFrame style={{background: 'radial-gradient(120% 90% at 65% 40%, #151C26 0%, #0B0F15 52%, #05070A 100%)', fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 120, top: 96, color: C.orange, fontSize: 19, fontWeight: 600, letterSpacing: '0.26em'}}>
        {eyebrow}
      </div>

      <div style={{position: 'absolute', left: 118, top: 156, width: 640, opacity: l1, transform: `translateY(${(1 - l1) * 18}px)`, fontFamily: DISPLAY, fontSize: 62, fontWeight: 600, lineHeight: 1.04, letterSpacing: '-0.035em', color: C.paper}}>
        {headline}
      </div>

      <div style={{position: 'absolute', left: 120, top: 356, opacity: l2, transform: `translateY(${(1 - l2) * 12}px)`, color: C.paper, fontSize: 40, letterSpacing: '-0.02em'}}>
        {values}
      </div>

      <div style={{position: 'absolute', left: 120, top: 432, width: 600, opacity: l3, transform: `translateY(${(1 - l3) * 12}px)`, color: 'rgba(244,241,234,0.72)', fontSize: 31, lineHeight: 1.4}}>
        {question}
      </div>

      <div style={{position: 'absolute', left: 120, top: 610, opacity: l4, transform: `translateY(${(1 - l4) * 10}px)`, color: C.orange, fontSize: 30, lineHeight: 1.35, width: 600}}>
        {punchline}
      </div>

      <div data-figure="fig1.67" style={{position: 'absolute', left: 760, top: 170, width: 1040, height: 470, background: C.paper, opacity: panel, transform: `scale(${0.96 + panel * 0.04})`, boxShadow: '0 30px 90px rgba(0,0,0,0.45)', border: '1px solid rgba(255,255,255,0.08)'}}>
        <Img src={staticFile(image)} style={{position: 'absolute', left: 30, top: 34, width: 980, height: 'auto'}} />
        <div style={{position: 'absolute', left: 44, top: 350, color: C.muted, fontSize: 19}}>{leftLabel}</div>
        <div style={{position: 'absolute', left: 580, top: 350, color: C.muted, fontSize: 19}}>{rightLabel}</div>
        <div style={{position: 'absolute', left: 44, right: 44, bottom: 34, height: 1, background: C.graph}} />
        <div data-source="fig1.67" style={{position: 'absolute', left: 44, right: 44, bottom: 12, color: C.muted, fontSize: 16, lineHeight: 1.4}}>
          {source}
        </div>
      </div>

      <div style={{position: 'absolute', left: 120, bottom: 130, opacity: src, color: 'rgba(244,241,234,0.4)', fontSize: 16, letterSpacing: '0.08em'}}>
        {footer}
      </div>
    </SceneFrame>
  );
};
