import React from 'react';
import {Composition} from 'remotion';
import {AccessProbe} from './compositions/AccessProbe';
import {ChapterCard, chapterCardDefaults} from './compositions/ChapterCard';
import {CourseTimeline} from './compositions/CourseTimeline';
import {CourseVideo} from './compositions/CourseVideo';
import {R1Smoke} from './compositions/R1Smoke';
import {ScenePage, ScenePageProps} from './compositions/ScenePage';
import {FormulaProbe} from './compositions/FormulaProbe';
import {PrimerPoc, primerPocDefaults} from './compositions/PrimerPoc';
import {PrimerQuad, primerQuadDefaults} from './compositions/PrimerQuad';
import {ShotsFile, TimelineSpec} from './types';
import {BRAND} from './brand/tokens';
import {BrandProps} from './brand/types';
import {CourseIntro} from './brand/CourseIntro';
import {CourseOutro} from './brand/CourseOutro';
import {NewsOutro} from './brand/NewsOutro';
import {ShortSignature} from './brand/ShortSignature';
import {BrandPreview} from './brand/BrandPreview';

const defaultProps: ShotsFile = {
  schema_version: 1,
  lesson: '01-shell-for-ai-era',
  timeline: {fps: 30, resolution: [1920, 1080], total_duration_s: 3},
  shots: [],
  annotations: [],
  narration: null,
  subtitles: null,
};

const brandDefaults: BrandProps = {
  durationInSeconds: BRAND.presets.course_intro.duration_s,
  title: 'The Transformer in Five Minutes',
  category: 'ENGINEERING EXPLAINED',
  date: '2026-11-09',
  showReservedArea: false,
};

const newsDefaults: BrandProps = {
  ...brandDefaults,
  durationInSeconds: BRAND.presets.news_outro.duration_s,
  category: 'INDUSTRY BRIEFING',
};

const brandMetadata = (fallbackSeconds: number) => ({props}: {props: BrandProps}) => ({
  durationInFrames: Math.max(1, Math.round((props.durationInSeconds ?? fallbackSeconds) * 30)),
  fps: 30,
});

const defaultTimeline: TimelineSpec = {
  schema_version: 1,
  kind: 'timeline_spec',
  lesson_id: 'preview',
  fps: {fps_num: 30, fps_den: 1},
  width: 1920,
  height: 1080,
  total_frames: 30,
  video: [],
  audio: [],
  subtitles: [],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CourseVideo"
        component={CourseVideo}
        durationInFrames={90}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultProps}
        calculateMetadata={({props}) => {
          const fps = props.timeline?.fps ?? 30;
          const total = props.timeline?.total_duration_s ?? 1;
          const resolution = props.timeline?.resolution ?? [1920, 1080];
          return {
            durationInFrames: Math.max(1, Math.round(total * fps)),
            fps,
            width: resolution[0],
            height: resolution[1],
          };
        }}
      />
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
        id="CourseTimeline"
        component={CourseTimeline}
        durationInFrames={30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={defaultTimeline}
        calculateMetadata={({props}) => {
          const fps = props.fps.fps_num / props.fps.fps_den;
          return {
            durationInFrames: Math.max(1, props.total_frames),
            fps,
            width: props.width,
            height: props.height,
          };
        }}
      />
      <Composition
        id="ScenePage"
        component={ScenePage}
        durationInFrames={30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          page: 1,
          total_pages: 12,
          section: 'Preview',
          title: 'Scene-first prototype',
          beats: [{at_s: 0, text: 'One idea at a time.'}],
          duration_s: 1,
        } as ScenePageProps}
        calculateMetadata={({props}) => ({
          durationInFrames: Math.max(1, Math.round(props.duration_s * 30)),
          fps: 30,
          width: 1920,
          height: 1080,
        })}
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
        id="BrandCourseIntro"
        component={CourseIntro}
        durationInFrames={105}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={brandDefaults}
        calculateMetadata={brandMetadata(BRAND.presets.course_intro.duration_s)}
      />
      <Composition
        id="BrandCourseOutro"
        component={CourseOutro}
        durationInFrames={360}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{...brandDefaults, durationInSeconds: BRAND.presets.course_outro.duration_s}}
        calculateMetadata={brandMetadata(BRAND.presets.course_outro.duration_s)}
      />
      <Composition
        id="BrandNewsOutro"
        component={NewsOutro}
        durationInFrames={180}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={newsDefaults}
        calculateMetadata={brandMetadata(BRAND.presets.news_outro.duration_s)}
      />
      <Composition
        id="BrandShortSignature"
        component={ShortSignature}
        durationInFrames={30}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={{...brandDefaults, durationInSeconds: BRAND.presets.short_signature.duration_s}}
        calculateMetadata={brandMetadata(BRAND.presets.short_signature.duration_s)}
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
