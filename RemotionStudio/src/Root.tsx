import React from 'react';
import {Composition} from 'remotion';
import {AccessProbe} from './compositions/AccessProbe';
import {CourseTimeline} from './compositions/CourseTimeline';
import {CourseVideo} from './compositions/CourseVideo';
import {R1Smoke} from './compositions/R1Smoke';
import {ScenePage, ScenePageProps} from './compositions/ScenePage';
import {FormulaProbe} from './compositions/FormulaProbe';
import {PrimerPoc, primerPocDefaults} from './compositions/PrimerPoc';
import {ShotsFile, TimelineSpec} from './types';

const defaultProps: ShotsFile = {
  schema_version: 1,
  lesson: '01-shell-for-ai-era',
  timeline: {fps: 30, resolution: [1920, 1080], total_duration_s: 3},
  shots: [],
  annotations: [],
  narration: null,
  subtitles: null,
};

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
    </>
  );
};
