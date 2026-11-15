import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {Formula} from './Formula';
import {C, DISPLAY, FONT, ease, win} from './theme';

const Parcels: React.FC<{t: number; fast: boolean}> = ({t, fast}) => {
  const rows = fast ? [90, 190] : [140];
  const count = fast ? 4 : 4;
  const gap = fast ? 120 : 150;
  const speed = fast ? 70 : 35;
  const arrow = fast ? 105 : 55;
  return (
    <svg viewBox="0 0 760 300" width="760" height="300">
      {rows.map((y, r) => (
        <g key={r}>
          {Array.from({length: count}).map((_, i) => {
            const base = 70 + i * gap;
            const x = base + ((t * speed + r * 40) % gap);
            const xx = x > 610 ? 70 + (x - 610) : x;
            return (
              <g key={i}>
                <rect x={xx} y={y} width={26} height={26} fill={fast ? C.orangeSoft : C.graph} stroke={fast ? C.orange : C.muted} strokeWidth={2} />
                <line x1={xx + 30} y1={y + 13} x2={xx + 30 + arrow} y2={y + 13} stroke={fast ? C.orange : C.muted} strokeWidth={3} />
                <path d={`M ${xx + 30 + arrow} ${y + 13} l -13 -6 v 12 z`} fill={fast ? C.orange : C.muted} />
              </g>
            );
          })}
        </g>
      ))}
      <path d="M 690 30 L 650 30 Q 620 30 620 60 L 620 250 Q 620 280 650 280 L 690 280 Z" fill={fast ? C.orangeSoft : C.graph} stroke={C.ink} strokeWidth={3} />
      <text x="630" y="296" fill={C.muted} fontFamily={FONT} fontSize="16">car</text>
    </svg>
  );
};

export type MechanismDiagramProps = {
  eyebrow?: string;
  title?: string;
  leftLabel?: string;
  leftNote?: string;
  rightLabel?: string;
  rightNote?: string;
};

export const MechanismScene: React.FC<MechanismDiagramProps> = ({
  eyebrow = 'T1-01 · 03 / THE MECHANISM',
  title = 'Why does 2× speed give 4× force?',
  leftLabel = 'speed v',
  leftNote = '4 parcels per second · momentum p',
  rightLabel = 'speed 2v',
  rightNote = '8 parcels per second · momentum 2p',
}) => {
  const t = useCurrentFrame() / 30;
  const q = ease(t / 0.8);
  const panels = ease((t - 4) / 0.8);
  const force = ease((t - 6) / 0.8);
  const power = ease((t - 9) / 0.8);
  const summary = ease((t - 12) / 0.8);

  return (
    <AbsoluteFill style={{background: 'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)', fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        {eyebrow}
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, width: 1600, opacity: q, transform: `translateY(${(1 - q) * 12}px)`, fontFamily: DISPLAY, fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper}}>
        {title}
      </div>

      <div style={{position: 'absolute', left: 120, top: 210, width: 760, opacity: panels}}>
        <div style={{color: C.paper, fontSize: 24, fontWeight: 600}}>{leftLabel}</div>
        <div style={{color: C.muted, fontSize: 17, marginTop: 4}}>{leftNote}</div>
        <Parcels t={t} fast={false} />
      </div>

      <div style={{position: 'absolute', left: 1000, top: 210, width: 760, opacity: panels}}>
        <div style={{color: C.orange, fontSize: 24, fontWeight: 600}}>{rightLabel}</div>
        <div style={{color: C.orange, fontSize: 17, marginTop: 4}}>{rightNote}</div>
        <Parcels t={t} fast />
      </div>

      <div style={{position: 'absolute', left: 120, top: 520, width: 820, opacity: force}}>
        {[
          {label: 'air parcels per second', value: '2×', share: 0.5},
          {label: 'momentum each', value: '2×', share: 0.5},
          {label: 'force on the car', value: '4×', share: 1},
        ].map((row) => (
          <div key={row.label} style={{display: 'flex', alignItems: 'center', height: 44}}>
            <div style={{width: 300, color: 'rgba(244,241,234,0.62)', fontSize: 18}}>{row.label}</div>
            <div style={{width: 300, height: 18, background: 'rgba(244,241,234,0.10)', position: 'relative'}}>
              <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: `${row.share * 100}%`, background: row.share === 1 ? C.orange : C.orangeSoft}} />
            </div>
            <div style={{marginLeft: 18, color: row.share === 1 ? C.orange : C.paper, fontSize: 22, fontWeight: 600}}>{row.value}</div>
          </div>
        ))}
      </div>

      <div style={{position: 'absolute', left: 120, top: 660, width: 1050, opacity: force}}>
        <div style={{color: 'rgba(244,241,234,0.55)', fontSize: 14, letterSpacing: '0.2em', marginBottom: 8}}>FORCE = MASS FLOW × VELOCITY CHANGE</div>
        <Formula tex={String.raw`\dot m=\rho A v,\qquad \Delta v=k\,v`} size={28} color={C.paper} />
        <div style={{height: 6}} />
        <Formula tex={String.raw`F=\dot m\,\Delta v=k\,\rho A v^2`} size={34} color={C.paper} />
        <div style={{marginTop: 8, color: C.orange, fontSize: 22}}>2× parcels &nbsp;×&nbsp; 2× momentum &nbsp;→&nbsp; <b>4× force</b></div>
      </div>

      <div style={{position: 'absolute', left: 120, top: 840, width: 1050, opacity: power}}>
        <div style={{color: 'rgba(244,241,234,0.55)', fontSize: 14, letterSpacing: '0.2em', marginBottom: 8}}>POWER = FORCE × SPEED</div>
        <Formula tex={String.raw`P=Fv=k\,\rho A v^3`} size={34} color={C.paper} />
        <div style={{marginTop: 8, color: C.orange, fontSize: 22}}>4× force &nbsp;×&nbsp; 2× speed &nbsp;→&nbsp; <b>8× power</b></div>
      </div>

      <div style={{position: 'absolute', left: 1000, top: 600, width: 760, opacity: summary, fontFamily: DISPLAY, fontSize: 32, fontWeight: 600, color: C.paper, letterSpacing: '-0.02em'}}>
        2× speed &nbsp;→&nbsp; <span style={{color: C.orange}}>4× force</span> &nbsp;→&nbsp; <span style={{color: C.orange}}>8× power</span>
      </div>

      <div style={{position: 'absolute', left: 120, bottom: 96, color: 'rgba(244,241,234,0.35)', fontSize: 14, letterSpacing: '0.1em'}}>
        SCHEMATIC · 1-D MOMENTUM MODEL · SAME SHAPE AND DENSITY · Ch. 3 §3.2.2 / §3.2.5 · k = momentum-defect factor (cD/2)
      </div>
    </AbsoluteFill>
  );
};
