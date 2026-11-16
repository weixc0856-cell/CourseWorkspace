import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {AnnotatedFigure} from '../components/AnnotatedFigure';

const overlays = [
  {kind: 'reveal' as const, from: 40, to: 700, at: 0.8},
  {kind: 'spotlight' as const, x: 740, y: 300, w: 90, h: 130, at: 1.4},
  {kind: 'label' as const, x: 120, y: 150, pointX: 780, pointY: 360, text: 'rear base pressure', at: 2.2},
];

const Root: React.FC = () => (
  <Composition
    id="PreviewAnnotated"
    component={AnnotatedFigure}
    durationInFrames={150}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{
      image: 'ref_figs/fig-1.77.png',
      imageWidth: 830,
      imageHeight: 570,
      eyebrow: 'T1-01 · 02 / WHERE DRAG LIVES',
      title: 'Pressure, not paint',
      source: 'Hucho, Aerodynamics of Road Vehicles, 5th ed., Fig. 1.77, p. 93 — unretouched',
      overlays,
      duration: 5,
    }}
  />
);
registerRoot(Root);
