import React from 'react';
import {Composition} from 'remotion';
import {AccessProbe} from './compositions/AccessProbe';
import {CourseVideo} from './compositions/CourseVideo';
import {ShotsFile} from './types';

const defaultProps: ShotsFile = {
  schema_version: 1,
  lesson: '01-shell-for-ai-era',
  timeline: {fps: 30, resolution: [1920, 1080], total_duration_s: 3},
  shots: [],
  annotations: [],
  narration: null,
  subtitles: null,
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
    </>
  );
};
