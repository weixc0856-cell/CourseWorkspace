import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {AnnotatedFigure} from '../components/AnnotatedFigure';

const overlays = [
  {kind: 'reveal' as const, from: 70, to: 660, at: 0.6},
  {kind: 'spotlight' as const, x: 450, y: 255, w: 200, h: 190, at: 1.2},
  {kind: 'spotlight' as const, x: 250, y: 650, w: 280, h: 130, at: 1.8},
  {kind: 'label' as const, x: 250, y: 230, pointX: 500, pointY: 330, text: 'three backs', at: 2.2},
  {kind: 'label' as const, x: 230, y: 760, pointX: 400, pointY: 690, text: 'separation', at: 2.8},
];

const Root: React.FC = () => (
  <Composition
    id="PreviewAnnotated136"
    component={AnnotatedFigure}
    durationInFrames={150}
    fps={30}
    width={1920}
    height={1080}
    defaultProps={{
      image: 'ref_figs/fig-1.36.png',
      imageWidth: 714,
      imageHeight: 807,
      eyebrow: 'T1-01 · 07 / WHY NOT A TEARDROP',
      title: 'The rear decides',
      source: 'Hucho, Aerodynamics of Road Vehicles, 5th ed., Fig. 1.36, p. 56 — unretouched',
      overlays,
      duration: 5,
    }}
  />
);
registerRoot(Root);
