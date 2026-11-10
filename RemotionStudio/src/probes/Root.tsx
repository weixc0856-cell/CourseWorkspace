import React from 'react';
import {Composition} from 'remotion';
import {AccessProbe} from './AccessProbe';
import {ChapterCard, chapterCardDefaults} from './ChapterCard';
import {FormulaProbe} from './FormulaProbe';
import {PrimerPoc, primerPocDefaults} from './PrimerPoc';
import {PrimerQuad, primerQuadDefaults} from './PrimerQuad';
import {R1Smoke} from './R1Smoke';
import {BRAND} from '../brand/tokens';
import {BrandPreview} from '../brand/BrandPreview';
import {BrandProps} from '../brand/types';

// Probe compositions. Render with `src/probes/index.ts`; they are not part of
// the production entry (`src/index.ts`) and must not appear in a course build.

const brandDefaults: BrandProps = {
  durationInSeconds: BRAND.presets.course_intro.duration_s,
  title: 'The Transformer in Five Minutes',
  category: 'ENGINEERING EXPLAINED',
  date: '2026-11-09',
  showReservedArea: false,
};

export const ProbeRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="AccessProbe"
        component={AccessProbe}
        durationInFrames={30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{src: '', kind: 'image' as const}}
      />
      <Composition
        id="ChapterCard"
        component={ChapterCard}
        durationInFrames={90}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={chapterCardDefaults}
      />
      <Composition
        id="PrimerQuad"
        component={PrimerQuad}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={primerQuadDefaults}
        calculateMetadata={({props}) => ({durationInFrames: Math.max(1, props.total_frames)})}
      />
      <Composition
        id="PrimerPoc"
        component={PrimerPoc}
        durationInFrames={900}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={primerPocDefaults}
      />
      <Composition
        id="FormulaProbe"
        component={FormulaProbe}
        durationInFrames={60}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{latex: 'a^2 + b^2 = c^2'}}
      />
      <Composition
        id="R1Smoke"
        component={R1Smoke}
        durationInFrames={150}
        fps={30}
        width={1920}
        height={1080}
      />
      <Composition
        id="BrandPreview"
        component={BrandPreview}
        durationInFrames={510}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={brandDefaults}
      />
    </>
  );
};
