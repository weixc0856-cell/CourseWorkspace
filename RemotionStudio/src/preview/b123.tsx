import React from 'react';
import {AbsoluteFill, Audio, Composition, Sequence, registerRoot, staticFile} from 'remotion';
import {AnnotatedFigure} from '../components/AnnotatedFigure';
import {FourForces} from '../components/FourForces';
import {FormulaBlock} from '../components/FormulaBlock';
import {DerivationCard} from '../components/DerivationCard';

// B1-B3 assembly against the measured 133.107 s voice track. Timings come
// from the synthesis meta, not from the old beat sheet.
const FPS = 30;
const f = (seconds: number) => Math.round(seconds * FPS);

const B123: React.FC = () => (
  <AbsoluteFill style={{background: '#05070A'}}>
    <Audio src={staticFile('preview-b123.wav')} />

    {/* B1 0.000-40.585 */}
    <Sequence from={0} durationInFrames={f(27) - 0}>
      <AnnotatedFigure
        image="ref_figs/fig-1.67.png"
        imageWidth={717}
        imageHeight={229}
        eyebrow="T1-01 · 01 / THE QUESTION"
        title="Same family. Two shapes."
        source="Hucho, 5th ed., Fig. 1.67, p. 82 — unretouched"
        duration={27}
        overlays={[
          {kind: 'spotlight', x: 40, y: 40, w: 620, h: 150, at: 0.8},
          {kind: 'label', x: 40, y: 34, pointX: 520, pointY: 120, text: 'cD 0.376 vs 0.27', at: 2.0},
        ]}
      />
    </Sequence>
    <Sequence from={f(27)} durationInFrames={f(41.185) - f(27)}>
      <FourForces duration={14.185} />
    </Sequence>

    {/* B2 41.185-77.883 */}
    <Sequence from={f(41.185)} durationInFrames={f(64) - f(41.185)}>
      <AnnotatedFigure
        image="ref_figs/fig-1.77.png"
        imageWidth={830}
        imageHeight={570}
        eyebrow="T1-01 · 02 / WHERE DRAG LIVES"
        title="Pressure, not paint"
        source="Hucho, 5th ed., Fig. 1.77, p. 93 — unretouched"
        duration={23}
        overlays={[
          {kind: 'reveal', from: 40, to: 700, at: 0.8},
          {kind: 'spotlight', x: 790, y: 170, w: 32, h: 150, at: 1.4},
          {kind: 'label', x: 870, y: 90, pointX: 805, pointY: 200, text: 'rear base pressure', at: 2.2},
        ]}
      />
    </Sequence>
    <Sequence from={f(64)} durationInFrames={f(77.883) - f(64)}>
      <AnnotatedFigure
        image="ref_figs/fig-1.73.png"
        imageWidth={577}
        imageHeight={209}
        eyebrow="T1-01 · 02 / WHERE DRAG LIVES"
        title="Where the field divides"
        source="Hucho, 5th ed., Fig. 1.73, p. 89 — unretouched"
        duration={14}
        overlays={[
          {kind: 'spotlight', x: 380, y: 60, w: 170, h: 130, at: 0.8},
          {kind: 'label', x: 40, y: 180, pointX: 460, pointY: 120, text: 'near wake', at: 1.6},
        ]}
      />
    </Sequence>

    {/* B3 77.883-133.107 */}
    <Sequence from={f(77.883)} durationInFrames={f(87) - f(77.883)}>
      <FormulaBlock tex={'F \\propto v^2'} title="1/6 · Why drag rises with speed" note="2x speed -> 4x force" duration={9.1} />
    </Sequence>
    <Sequence from={f(87)} durationInFrames={f(96.5) - f(87)}>
      <FormulaBlock tex={'P \\propto v^3'} title="2/6 · Why power rises faster" note="2x speed -> 8x power" duration={9.5} />
    </Sequence>
    <Sequence from={f(96.5)} durationInFrames={f(107.336) - f(96.5)}>
      <FormulaBlock tex={'60 \\to 190\\,km/h \\approx 10\\times'} title="3/6 · The same ratio in real numbers" note="the same ratio, ten times the force" duration={10.8} />
    </Sequence>
    <Sequence from={f(107.336)} durationInFrames={f(120) - f(107.336)}>
      <DerivationCard duration={12.7} />
    </Sequence>
    <Sequence from={f(120)} durationInFrames={f(126.5) - f(120)}>
      <FormulaBlock tex={'c_D\\,\\text{same},\\; A\\,\\text{different}'} title="5/6 · One coefficient, two cars" note="same coefficient, different area" duration={6.5} />
    </Sequence>
    <Sequence from={f(126.5)} durationInFrames={f(133.107) - f(126.5)}>
      <FormulaBlock tex={'c_D A'} title="6/6 · The product that sets drag" note="the product is what the air sees" duration={6.6} />
    </Sequence>
  </AbsoluteFill>
);

const Root: React.FC = () => (
  <Composition
    id="PreviewB123"
    component={B123}
    durationInFrames={f(133.107)}
    fps={FPS}
    width={854}
    height={480}
  />
);
registerRoot(Root);
