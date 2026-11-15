import React from 'react';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {C, DISPLAY, FONT, ease} from './theme';

export type ChartOverlayProps = {
  image?: string;
  eyebrow?: string;
  title?: string;
  source?: string;
  crossValue?: string;
  crossNote?: string;
  tenValue?: string;
  tenNote?: string;
  footnote?: React.ReactNode;
};

export const EvidenceScene: React.FC<ChartOverlayProps> = ({
  image = 'staging/t1-01-why-aerodynamics/fig3-9-tight.png',
  eyebrow = 'T1-01 · 04 / THE EVIDENCE',
  title = 'The book’s chart agrees.',
  source = 'Fig. 3.9, p. 160 · Schuetz (ed.), Aerodynamics of Road Vehicles, 5th ed.',
  crossValue = '≈ 60 km/h',
  crossNote = 'where rolling resistance and aerodynamic drag swap places',
  tenValue = '10×',
  tenNote = 'the drag at 190 km/h, compared with 60',
  footnote = (
    <>
      A 5% grade pulls as hard as the air at 150 km/h.
      <br />1 m/s² of acceleration, as hard as the air at 230.
    </>
  ),
}) => {
  const t = useCurrentFrame() / 30;
  const q = ease(t / 0.8);
  const panel = ease((t - 1) / 1);
  const cross = ease((t - 6) / 0.9);
  const ten = ease((t - 16) / 0.9);
  const src = ease((t - 12) / 0.8);

  const z = t < 15 ? 1 + 0.06 * ease((t - 5) / 9) : 1.06 - 0.03 * ease((t - 15) / 9);
  const px = t < 15 ? 0 : -35 * ease((t - 15) / 9);

  return (
    <AbsoluteFill style={{background: 'radial-gradient(110% 90% at 40% 40%, #111A24 0%, #080C12 60%, #05070A 100%)', fontFamily: FONT}}>
      <div style={{position: 'absolute', left: 96, top: 96, color: C.orange, fontSize: 18, fontWeight: 600, letterSpacing: '0.26em'}}>
        {eyebrow}
      </div>
      <div style={{position: 'absolute', left: 96, top: 132, opacity: q, transform: `translateY(${(1 - q) * 12}px)`, fontFamily: DISPLAY, fontSize: 44, fontWeight: 600, letterSpacing: '-0.03em', color: C.paper}}>
        {title}
      </div>

      <div data-evidence="fig3-9" style={{position: 'absolute', left: 100, top: 190, width: 1120, height: 680, background: C.paper, opacity: panel, boxShadow: '0 30px 90px rgba(0,0,0,0.45)', overflow: 'hidden'}}>
        <div style={{position: 'absolute', inset: 0, transform: `scale(${z}) translateX(${px}px)`, transformOrigin: '38% 82%'}}>
          <Img src={staticFile(image)} style={{position: 'absolute', left: 40, top: 20, width: 960, height: 'auto'}} />
        </div>
        <div style={{position: 'absolute', left: 34, bottom: 10, color: C.muted, fontSize: 14}}>
          {source}
        </div>
      </div>

      <div style={{position: 'absolute', left: 1244, top: 214, width: 580, opacity: cross, transform: `translateY(${(1 - cross) * 12}px)`}}>
        <div style={{fontFamily: DISPLAY, fontSize: 64, fontWeight: 600, color: C.orange, lineHeight: 1, letterSpacing: '-0.04em'}}>{crossValue}</div>
        <div style={{marginTop: 12, color: 'rgba(244,241,234,0.65)', fontSize: 22, lineHeight: 1.5}}>{crossNote}</div>
      </div>

      <div style={{position: 'absolute', left: 1244, top: 430, width: 580, opacity: ten, transform: `translateY(${(1 - ten) * 12}px)`}}>
        <div style={{fontFamily: DISPLAY, fontSize: 92, fontWeight: 600, color: C.paper, lineHeight: 1, letterSpacing: '-0.05em'}}>{tenValue}</div>
        <div style={{marginTop: 10, color: 'rgba(244,241,234,0.65)', fontSize: 22, lineHeight: 1.5}}>{tenNote}</div>
      </div>

      <div style={{position: 'absolute', left: 1244, top: 660, width: 580, opacity: src, paddingTop: 16, borderTop: '1px solid rgba(244,241,234,0.16)', color: C.paper, fontSize: 22, lineHeight: 1.55}}>
        {footnote}
      </div>

      <div style={{position: 'absolute', left: 96, bottom: 96, color: 'rgba(244,241,234,0.35)', fontSize: 14, letterSpacing: '0.1em'}}>
        BOOK FIGURE · B-CLASS · TABLE 3.1 · §3.2.6
      </div>
    </AbsoluteFill>
  );
};
