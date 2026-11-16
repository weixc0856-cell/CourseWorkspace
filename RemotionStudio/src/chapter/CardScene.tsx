import React from 'react';
import {SceneFrame} from './SceneFrame';
import {useSceneTime} from './timing';
import {C, DISPLAY, FONT, ease} from './theme';

export type CardVariant = 'date' | 'statement' | 'chain' | 'not_claimed' | 'end';

export type CardProps = {
  text?: string;
  eyebrow?: string;
  tier?: string;
  source?: string;
  variant?: CardVariant;
  duration?: number;
};

const BG = 'radial-gradient(110% 90% at 40% 40%, #111A24 0%, #080C12 60%, #05070A 100%)';

export const CardScene: React.FC<CardProps> = ({
  text = '',
  eyebrow = '',
  tier = '',
  source = '',
  variant = 'statement',
  duration,
}) => {
  const t = useSceneTime(duration);
  const a = ease(t / 0.7);

  const chrome = (
    <>
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        {eyebrow}
      </div>
      {tier ? (
        <div style={{position: 'absolute', right: 96, bottom: 150, color: C.cyan, fontSize: 17, letterSpacing: '0.2em'}}>
          {tier}
        </div>
      ) : null}
      {source ? (
        <div style={{position: 'absolute', left: 96, bottom: 150, width: 1400, color: 'rgba(244,241,234,0.66)', fontSize: 16}}>
          {source}
        </div>
      ) : null}
    </>
  );

  if (variant === 'date') {
    return (
      <SceneFrame style={{background: BG, fontFamily: FONT}}>
        <div style={{position: 'absolute', left: 96, top: 380, opacity: a, transform: `translateY(${(1 - a) * 16}px)`, fontFamily: DISPLAY, fontSize: 150, fontWeight: 700, letterSpacing: '-0.045em', color: C.paper}}>
          {text}
        </div>
        {chrome}
      </SceneFrame>
    );
  }

  if (variant === 'chain') {
    const parts = text.split('·').map((p) => p.trim()).filter(Boolean);
    return (
      <SceneFrame style={{background: BG, fontFamily: FONT}}>
        <div style={{position: 'absolute', left: 96, top: 430, display: 'flex', alignItems: 'center', gap: 22, opacity: a}}>
          {parts.map((p, i) => (
            <React.Fragment key={p + i}>
              {i > 0 && <span style={{color: C.cyan, fontSize: 34}}>→</span>}
              <span style={{fontFamily: DISPLAY, fontSize: 46, fontWeight: 600, color: C.paper, letterSpacing: '-0.02em', opacity: ease((t - i * 0.25) / 0.5)}}>
                {p}
              </span>
            </React.Fragment>
          ))}
        </div>
        {chrome}
      </SceneFrame>
    );
  }

  if (variant === 'not_claimed') {
    return (
      <SceneFrame style={{background: BG, fontFamily: FONT}}>
        <div style={{position: 'absolute', left: 96, top: 300, width: 1600, opacity: a, fontFamily: DISPLAY, fontSize: 42, fontWeight: 600, lineHeight: 1.7, color: C.paper}}>
          {text}
        </div>
        {chrome}
      </SceneFrame>
    );
  }

  if (variant === 'end') {
    return (
      <SceneFrame style={{background: BG, fontFamily: FONT}}>
        <div style={{position: 'absolute', left: 0, right: 0, top: 470, textAlign: 'center', opacity: a, letterSpacing: '0.34em', fontSize: 30, color: C.paper}}>
          {text}
        </div>
        {chrome}
      </SceneFrame>
    );
  }

  return (
    <SceneFrame style={{background: BG, fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 96, top: 420, width: 1650, opacity: a, transform: `translateY(${(1 - a) * 14}px)`, fontFamily: DISPLAY, fontSize: 56, fontWeight: 600, lineHeight: 1.35, letterSpacing: '-0.02em', color: C.paper}}>
        {text}
      </div>
      {chrome}
    </SceneFrame>
  );
};
