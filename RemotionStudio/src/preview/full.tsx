import React from 'react';
import {AbsoluteFill, Audio, Composition, Sequence, registerRoot, staticFile} from 'remotion';
import {AnnotatedFigure} from '../components/AnnotatedFigure';
import {FourForces} from '../components/FourForces';
import {FormulaBlock} from '../components/FormulaBlock';
import {DerivationCard} from '../components/DerivationCard';
import {PointsCard} from '../components/PointsCard';
import {RearShapeDiagram} from '../components/RearShapeDiagram';
import {CarScene} from '../chapter/CarScene';

// Full film assembly against the measured 320.902 s narration. Cuts sit on
// the measured segment starts, not on the retired beat sheet.
const FPS = 30;
const f = (s: number) => Math.round(s * FPS);

const fig = (id: string) => `ref_figs/fig-${id}.png`;

const Film: React.FC = () => (
  <AbsoluteFill style={{background: '#05070A'}}>
    <Audio src={staticFile('preview-full.wav')} />

    {/* B1 0.000-36.502 */}
    <Sequence from={0} durationInFrames={f(18)}>
      <AnnotatedFigure
        image={fig('1.67')} imageWidth={717} imageHeight={229}
        eyebrow="T1-01 · 01 / THE QUESTION" title="Same family. Two shapes."
        source="Hucho, 5th ed., Fig. 1.67, p. 82 — unretouched" duration={18}
        overlays={[
          {kind: 'spotlight', x: 40, y: 40, w: 620, h: 150, at: 0.8},
          {kind: 'label', x: 40, y: 34, pointX: 520, pointY: 120, text: 'cD 0.376 vs 0.27', at: 2.0},
        ]}
      />
    </Sequence>
    <Sequence from={f(18)} durationInFrames={f(36.502) - f(18)}>
      <FourForces duration={18.5} />
    </Sequence>

    {/* B2 36.502-74.566 */}
    <Sequence from={f(36.502)} durationInFrames={f(55) - f(36.502)}>
      <AnnotatedFigure
        image={fig('1.77')} imageWidth={830} imageHeight={570}
        eyebrow="T1-01 · 02 / WHERE DRAG LIVES" title="Pressure, not paint"
        source="Hucho, 5th ed., Fig. 1.77, p. 93 — unretouched" duration={18.5}
        overlays={[
          {kind: 'reveal', from: 40, to: 700, at: 0.8},
          {kind: 'spotlight', x: 790, y: 170, w: 32, h: 150, at: 1.4},
          {kind: 'label', x: 870, y: 90, pointX: 805, pointY: 200, text: 'rear base pressure', at: 2.2},
        ]}
      />
    </Sequence>
    <Sequence from={f(55)} durationInFrames={f(74.566) - f(55)}>
      <AnnotatedFigure
        image={fig('1.73')} imageWidth={577} imageHeight={209}
        eyebrow="T1-01 · 02 / WHERE DRAG LIVES" title="Where the field divides"
        source="Hucho, 5th ed., Fig. 1.73, p. 89 — unretouched" duration={19.5}
        overlays={[
          {kind: 'spotlight', x: 380, y: 60, w: 170, h: 130, at: 0.8},
          {kind: 'label', x: 40, y: 180, pointX: 460, pointY: 120, text: 'near wake', at: 1.6},
        ]}
      />
    </Sequence>

    {/* B3 74.566-128.034 */}
    <Sequence from={f(74.566)} durationInFrames={f(84) - f(74.566)}>
      <FormulaBlock tex={'F \\propto v^2'} title="1/6 · Why drag rises with speed" note="2x speed -> 4x force" duration={9.4} />
    </Sequence>
    <Sequence from={f(84)} durationInFrames={f(94) - f(84)}>
      <FormulaBlock tex={'P \\propto v^3'} title="2/6 · Why power rises faster" note="2x speed -> 8x power" duration={10} />
    </Sequence>
    <Sequence from={f(94)} durationInFrames={f(104.8) - f(94)}>
      <FormulaBlock tex={'60 \\to 190\\,km/h \\approx 10\\times'} title="3/6 · The same ratio in real numbers" note="the same ratio, ten times the force" duration={10.8} />
    </Sequence>
    <Sequence from={f(104.8)} durationInFrames={f(114) - f(104.8)}>
      <DerivationCard duration={9.2} />
    </Sequence>
    <Sequence from={f(114)} durationInFrames={f(121) - f(114)}>
      <FormulaBlock tex={'c_D\\,\\text{same},\\; A\\,\\text{different}'} title="5/6 · One coefficient, two cars" note="same coefficient, different area" duration={7} />
    </Sequence>
    <Sequence from={f(121)} durationInFrames={f(128.034) - f(121)}>
      <FormulaBlock tex={'c_D A'} title="6/6 · The product that sets drag" note="the product is what the air sees" duration={7} />
    </Sequence>

    {/* B4 128.034-168.634 */}
    <Sequence from={f(128.034)} durationInFrames={f(150) - f(128.034)}>
      <CarScene duration={22} eyebrow="T1-01 · 04 / THE NUMBERS" headline="At 120 km/h the air takes three times the rolling bill." />
    </Sequence>
    <Sequence from={f(150)} durationInFrames={f(168.634) - f(150)}>
      <AnnotatedFigure
        image={fig('1.7')} imageWidth={532} imageHeight={379}
        eyebrow="T1-01 · 04 / THE NUMBERS" title="Frontal area is a multiplier"
        source="Hucho, 5th ed., Fig. 1.7, p. 31 — unretouched" duration={18.6}
      />
    </Sequence>

    {/* B5 168.634-199.087 */}
    <Sequence from={f(168.634)} durationInFrames={f(184) - f(168.634)}>
      <AnnotatedFigure
        image={fig('3.9')} imageWidth={708} imageHeight={412}
        eyebrow="T1-01 · 05 / THE CROSSOVER" title="The crossover sits near sixty"
        source="Hucho, 5th ed., Fig. 3.9, p. 181 — unretouched" duration={15.4}
      />
    </Sequence>
    <Sequence from={f(184)} durationInFrames={f(199.087) - f(184)}>
      <AnnotatedFigure
        image={fig('1.63')} imageWidth={844} imageHeight={483}
        eyebrow="T1-01 · 05 / THE CROSSOVER" title="Sixty years of cD"
        source="Hucho, 5th ed., Fig. 1.63, p. 79 — unretouched" duration={15.1}
      />
    </Sequence>

    {/* B6 199.087-229.541 */}
    <Sequence from={f(199.087)} durationInFrames={f(214) - f(199.087)}>
      <AnnotatedFigure
        image={fig('1.56')} imageWidth={530} imageHeight={429}
        eyebrow="T1-01 · 06 / THE GOLF CASE" title="Same coefficient. Different area."
        source="Hucho, 5th ed., Fig. 1.56, p. 74 — unretouched" duration={14.9}
      />
    </Sequence>
    <Sequence from={f(214)} durationInFrames={f(229.541) - f(214)}>
      <AnnotatedFigure
        image={fig('3.2')} imageWidth={838} imageHeight={311}
        eyebrow="T1-01 · 06 / THE GOLF CASE" title="Area grew with the body"
        source="Hucho, 5th ed., Fig. 3.2, p. 174 — unretouched" duration={15.5}
      />
    </Sequence>

    {/* B7 229.541-259.214 */}
    <Sequence from={f(229.541)} durationInFrames={f(244) - f(229.541)}>
      <AnnotatedFigure
        image={fig('1.36')} imageWidth={714} imageHeight={807}
        eyebrow="T1-01 · 07 / WHY NOT A TEARDROP" title="The rear decides"
        source="Hucho, 5th ed., Fig. 1.36, p. 56 — unretouched" duration={14.5}
        overlays={[
          {kind: 'reveal', from: 70, to: 660, at: 0.6},
          {kind: 'spotlight', x: 450, y: 255, w: 200, h: 190, at: 1.2},
          {kind: 'label', x: 250, y: 230, pointX: 500, pointY: 330, text: 'three backs', at: 2.2},
        ]}
      />
    </Sequence>
    <Sequence from={f(244)} durationInFrames={f(259.214) - f(244)}>
      <RearShapeDiagram duration={15.2} />
    </Sequence>

    {/* B8 259.214-291.619 */}
    <Sequence from={f(259.214)} durationInFrames={f(275) - f(259.214)}>
      <AnnotatedFigure
        image={fig('1.40')} imageWidth={851} imageHeight={459}
        eyebrow="T1-01 · 08 / WHEN IT BROKE" title="A slanted back can fight you"
        source="Hucho, 5th ed., Fig. 1.40, p. 59 — unretouched" duration={15.8}
      />
    </Sequence>
    <Sequence from={f(275)} durationInFrames={f(291.619) - f(275)}>
      <AnnotatedFigure
        image={fig('1.75')} imageWidth={649} imageHeight={567}
        eyebrow="T1-01 · 08 / WHEN IT BROKE" title="Where the vortex sits"
        source="Hucho, 5th ed., Fig. 1.75, p. 91 — unretouched" duration={16.6}
      />
    </Sequence>

    {/* B9 291.619-320.902 */}
    <Sequence from={f(291.619)} durationInFrames={f(305) - f(291.619)}>
      <PointsCard duration={13.4} />
    </Sequence>
    <Sequence from={f(305)} durationInFrames={f(314) - f(305)}>
      <CarScene duration={9} eyebrow="T1-01 · 09 / WHAT TO KEEP" headline="Shape is the energy bill." />
    </Sequence>
    <Sequence from={f(314)} durationInFrames={f(320.902) - f(314)}>
      <AnnotatedFigure
        image={fig('1.68')} imageWidth={481} imageHeight={355}
        eyebrow="T1-01 · 09 / WHAT TO KEEP" title="Shape is an intersection"
        source="Hucho, 5th ed., Fig. 1.68, p. 83 — unretouched" duration={6.9}
      />
    </Sequence>
  </AbsoluteFill>
);

const Root: React.FC = () => (
  <Composition
    id="FilmT101"
    component={Film}
    durationInFrames={f(320.902)}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
registerRoot(Root);
