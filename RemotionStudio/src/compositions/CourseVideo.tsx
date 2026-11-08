import React from 'react';
import {
  AbsoluteFill,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {Narration} from '../audio/Narration';
import {Annotations} from '../overlays/Annotations';
import {Captions} from '../subtitles/Captions';
import {COLORS} from '../styles/tokens';
import {Presentation, Shot, ShotsFile} from '../types';
import {secondsToFrames, stagingPath} from '../utils/timing';

const videoStyle: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'cover',
};

const Fade: React.FC<{durationInFrames: number; children: React.ReactNode}> = ({
  durationInFrames,
  children,
}) => {
  const frame = useCurrentFrame();
  if (durationInFrames < 4) return <AbsoluteFill>{children}</AbsoluteFill>;
  const fade = Math.min(9, Math.max(1, Math.floor(durationInFrames / 2)));
  const opacity = interpolate(
    frame,
    [0, fade, durationInFrames - fade, durationInFrames],
    [0, 1, 1, 0],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  return <AbsoluteFill style={{opacity}}>{children}</AbsoluteFill>;
};

const BaseShot: React.FC<{lesson: string; shot: Shot; fps: number}> = ({
  lesson,
  shot,
  fps,
}) => {
  const from = secondsToFrames(shot.start_s, fps);
  const durationInFrames = Math.max(1, secondsToFrames(shot.duration_s, fps));
  const src = staticFile(stagingPath(lesson, shot.source));

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={`${shot.id}:base`}>
      {shot.kind === 'recording' ? (
        <OffthreadVideo src={src} style={videoStyle} />
      ) : (
        <Img src={src} style={videoStyle} />
      )}
    </Sequence>
  );
};

const OverlayContent: React.FC<{
  lesson: string;
  shot: Shot;
  presentation: Presentation;
}> = ({lesson, shot, presentation}) => {
  const src = staticFile(stagingPath(lesson, shot.source));

  if (presentation === 'picture_in_picture') {
    return (
      <AbsoluteFill
        style={{justifyContent: 'flex-end', alignItems: 'flex-end', padding: 48}}
      >
        <div
          style={{
            width: '42%',
            aspectRatio: '16 / 9',
            border: `4px solid ${COLORS.orange}`,
            boxShadow: '0 12px 40px rgba(0,0,0,0.25)',
            overflow: 'hidden',
            background: COLORS.white,
          }}
        >
          <OffthreadVideo src={src} style={videoStyle} />
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill
      style={{backgroundColor: presentation === 'cutaway' ? COLORS.paper : 'transparent'}}
    >
      <OffthreadVideo
        src={src}
        style={{
          ...videoStyle,
          objectFit: presentation === 'transparent_overlay' ? 'contain' : 'cover',
        }}
      />
    </AbsoluteFill>
  );
};

const OverlayShot: React.FC<{lesson: string; shot: Shot; fps: number}> = ({
  lesson,
  shot,
  fps,
}) => {
  if (!shot.presentation) {
    throw new Error(`overlay shot ${shot.id} is missing presentation`);
  }
  const from = secondsToFrames(shot.start_s, fps);
  const durationInFrames = Math.max(1, secondsToFrames(shot.duration_s, fps));

  return (
    <Sequence from={from} durationInFrames={durationInFrames} name={`${shot.id}:overlay`}>
      <Fade durationInFrames={durationInFrames}>
        <OverlayContent lesson={lesson} shot={shot} presentation={shot.presentation} />
      </Fade>
    </Sequence>
  );
};

export const CourseVideo: React.FC<ShotsFile> = (props) => {
  const {fps} = useVideoConfig();
  const shots = props.shots ?? [];

  if (shots.length === 0) {
    return <AbsoluteFill style={{backgroundColor: COLORS.paper}} />;
  }

  const baseShots = shots.filter((shot) => shot.timeline_role === 'base');
  const overlayShots = shots.filter((shot) => shot.timeline_role === 'overlay');

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper}}>
      {baseShots.map((shot) => (
        <BaseShot key={shot.id} lesson={props.lesson} shot={shot} fps={fps} />
      ))}
      {overlayShots.map((shot) => (
        <OverlayShot key={shot.id} lesson={props.lesson} shot={shot} fps={fps} />
      ))}
      <Annotations annotations={props.annotations ?? null} />
      {props.captions !== false ? (
        <Captions lesson={props.lesson} subtitles={props.subtitles ?? null} />
      ) : null}
      <Narration lesson={props.lesson} narration={props.narration ?? null} />
    </AbsoluteFill>
  );
};
