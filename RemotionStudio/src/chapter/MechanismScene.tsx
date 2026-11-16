import React from 'react';
import {SceneFrame} from './SceneFrame';
import {useSceneTime} from './timing';
import {Formula} from './Formula';
import {C, DISPLAY, FONT, ease} from './theme';

// Layout contract: docs/生产合同.md §9. The lower half is a set of fixed bands
// and nothing may leave its band. Bands exist because the previous version
// positioned blocks by hand and, after about 17 s, the formula stack, the
// inference lines and the footer were drawn on top of each other.
const BAND = {
  title: {top: 0, bottom: 200},
  mechanism: {top: 200, bottom: 560},
  formula: {top: 560, bottom: 840},
  conclusion: {top: 840, bottom: 920},
  footer: {top: 920, bottom: 950},
} as const;

const Parcels: React.FC<{t: number; fast: boolean}> = ({t, fast}) => {
  const rows = fast ? [90, 190] : [140];
  const count = 4;
  const gap = fast ? 120 : 150;
  const speed = fast ? 70 : 35;
  const arrow = fast ? 105 : 55;
  return (
    <svg viewBox="0 0 760 300" width="760" height="290">
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
      <g>
        <path
          d="M 690 218 L 690 166 L 662 160 L 642 116 Q 630 94 604 94 L 512 94 Q 486 94 470 116 L 452 160 L 420 166 L 420 218 Z"
          fill={fast ? C.orangeSoft : C.graph}
          stroke={C.ink}
          strokeWidth={3}
        />
        <circle cx="474" cy="220" r="20" fill={C.ink} stroke={C.muted} strokeWidth="3" />
        <circle cx="628" cy="220" r="20" fill={C.ink} stroke={C.muted} strokeWidth="3" />
        <line x1="420" y1="166" x2="420" y2="218" stroke={fast ? C.orange : C.muted} strokeWidth="4" />
        <text x="520" y="240" fill={C.muted} fontFamily={FONT} fontSize="16">car · front face</text>
      </g>
    </svg>
  );
};

const Band: React.FC<{
  band: keyof typeof BAND;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({band, children, style}) => (
  <div
    style={{
      position: 'absolute',
      left: 96,
      right: 96,
      top: BAND[band].top,
      height: BAND[band].bottom - BAND[band].top,
      ...style,
    }}
  >
    {children}
  </div>
);

export type MechanismDiagramProps = {
  duration?: number;
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
  duration,
}) => {
  const t = useSceneTime(duration);

  // Staged reveal. At most two main formulas are on screen at any moment: the
  // live one in the formula band and the one just established above it.
  const q = ease(t / 0.8);
  const panels = ease((t - 2) / 0.8);
  const bars = ease((t - 5) / 0.8);
  const massFlow = ease((t - 7) / 0.8);
  const forceLaw = ease((t - 10) / 0.8);
  const forceLine = ease((t - 12) / 0.8);
  const powerLaw = ease((t - 16) / 0.8);
  const powerLine = ease((t - 18) / 0.8);
  const summary = ease((t - 20) / 0.8);

  const live = powerLaw > 0.2 ? 'power' : forceLaw > 0.2 ? 'force' : 'mass';

  return (
    <SceneFrame style={{background: 'radial-gradient(110% 90% at 50% 30%, #111A24 0%, #080C12 60%, #05070A 100%)', fontFamily: FONT}}>
      <Band band="title">
        <div style={{position: 'absolute', left: 24, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>{eyebrow}</div>
        <div style={{position: 'absolute', left: 24, top: 128, opacity: q, transform: `translateY(${(1 - q) * 12}px)`, fontFamily: DISPLAY, fontSize: 40, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper}}>
          {title}
        </div>
      </Band>

      <Band band="mechanism" style={{opacity: panels}}>
        <div style={{position: 'absolute', left: 24, top: 16, width: 760}}>
          <div style={{color: C.paper, fontSize: 24, fontWeight: 600}}>{leftLabel}</div>
          <div style={{color: C.muted, fontSize: 17, marginTop: 4}}>{leftNote}</div>
          <Parcels t={t} fast={false} />
        </div>
        <div style={{position: 'absolute', left: 904, top: 16, width: 760}}>
          <div style={{color: C.orange, fontSize: 24, fontWeight: 600}}>{rightLabel}</div>
          <div style={{color: C.orange, fontSize: 17, marginTop: 4}}>{rightNote}</div>
          <Parcels t={t} fast />
        </div>
      </Band>

      <Band band="formula">
        <div style={{position: 'absolute', left: 24, top: 10, width: 700, opacity: bars}}>
          {[
            {label: 'air parcels per second', value: '2×', share: 0.5},
            {label: 'momentum each', value: '2×', share: 0.5},
            {label: 'force on the car', value: '4×', share: 1},
          ].map((row) => (
            <div key={row.label} style={{display: 'flex', alignItems: 'center', height: 44}}>
              <div style={{width: 300, color: 'rgba(244,241,234,0.62)', fontSize: 18}}>{row.label}</div>
              <div style={{width: 240, height: 18, background: 'rgba(244,241,234,0.10)', position: 'relative'}}>
                <div style={{position: 'absolute', left: 0, top: 0, bottom: 0, width: `${row.share * 100}%`, background: row.share === 1 ? C.orange : C.orangeSoft}} />
              </div>
              <div style={{marginLeft: 18, color: row.share === 1 ? C.orange : C.paper, fontSize: 22, fontWeight: 600}}>{row.value}</div>
            </div>
          ))}
        </div>

        <div style={{position: 'absolute', left: 1140, top: 0, width: 560, opacity: bars}}>
          <div style={{color: 'rgba(244,241,234,0.55)', fontSize: 14, letterSpacing: '0.2em', marginBottom: 8}}>MASS FLOW = DENSITY × AREA × SPEED</div>
          <svg viewBox="0 0 560 240" width="560" height="240">
            <rect x="10" y="0" width="230" height="200" fill="none" stroke={C.muted} strokeWidth={3} />
            <rect x="300" y="0" width="230" height="200" fill="none" stroke={C.orange} strokeWidth={3} />
            {[0, 1, 2, 3].map((i) => (
              <circle key={`a${i}`} cx={32 + (i % 2) * 90} cy={40 + Math.floor(i / 2) * 100} r="12" fill={C.graph} />
            ))}
            {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
              <circle key={`b${i}`} cx={322 + (i % 2) * 90} cy={34 + Math.floor(i / 2) * 48} r="12" fill={C.orange} />
            ))}
            <text x="60" y="228" fill={C.muted} fontFamily={FONT} fontSize="15">4 parcels / s</text>
            <text x="348" y="228" fill={C.orange} fontFamily={FONT} fontSize="15">8 parcels / s</text>
          </svg>
        </div>

        <div style={{position: 'absolute', left: 24, top: 150, width: 1060}}>
          <div style={{color: 'rgba(244,241,234,0.55)', fontSize: 14, letterSpacing: '0.2em', marginBottom: 6}}>
            {live === 'power' ? 'POWER = FORCE × SPEED' : 'FORCE = MASS FLOW × VELOCITY CHANGE'}
          </div>
          {live === 'power' ? (
            <div style={{opacity: powerLaw}}>
              <Formula tex={String.raw`P=Fv=k\,\rho A v^3`} size={34} color={C.paper} />
            </div>
          ) : (
            <div style={{opacity: massFlow * (1 - powerLaw)}}>
              <Formula tex={String.raw`\dot m=\rho A v,\qquad \Delta v=k\,v`} size={26} color={C.paper} />
            </div>
          )}
          <div style={{marginTop: 6, opacity: forceLaw * (1 - powerLaw)}}>
            <Formula tex={String.raw`F=\dot m\,\Delta v=k\,\rho A v^2`} size={30} color={C.paper} />
          </div>
        </div>
      </Band>

      <Band band="conclusion">
        {/* Both inference lines stay on screen: the 4x chain is what the power
            line is built on, so fading it out would delete the argument. */}
        <div style={{position: 'absolute', left: 24, top: 6, opacity: forceLine, color: C.orange, fontSize: 22}}>
          2× parcels &nbsp;×&nbsp; 2× momentum &nbsp;→&nbsp; <b>4× force</b>
        </div>
        <div style={{position: 'absolute', left: 24, top: 46, opacity: powerLine, color: C.orange, fontSize: 22}}>
          4× force &nbsp;×&nbsp; 2× speed &nbsp;→&nbsp; <b>8× power</b>
        </div>
        <div style={{position: 'absolute', right: 24, top: 4, opacity: summary, fontFamily: DISPLAY, fontSize: 30, fontWeight: 600, color: C.paper, letterSpacing: '-0.02em'}}>
          2× speed &nbsp;→&nbsp; <span style={{color: C.orange}}>4× force</span> &nbsp;→&nbsp; <span style={{color: C.orange}}>8× power</span>
        </div>
      </Band>

      <Band band="footer">
        <div style={{position: 'absolute', left: 24, top: 12, color: 'rgba(244,241,234,0.35)', fontSize: 14, letterSpacing: '0.1em'}}>
          SCHEMATIC · 1-D MOMENTUM MODEL · SAME SHAPE AND DENSITY · Ch. 3 §3.2.2 / §3.2.5 · k = momentum-defect factor (cD/2)
        </div>
      </Band>
    </SceneFrame>
  );
};
