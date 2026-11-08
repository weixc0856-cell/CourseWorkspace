import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import {KenBurnsMotion, MotionImage} from '../components/MotionImage';
import {Annotations} from '../overlays/Annotations';
import {COLORS, FONTS} from '../styles/tokens';
import {
  Annotation,
  Presentation,
  TimelineAudio,
  TimelineCue,
  TimelineSpec,
  TimelineVideo,
} from '../types';
import {stagingPath} from '../utils/timing';

const videoStyle: React.CSSProperties = {
  width: '100%',
  height: '100%',
  objectFit: 'cover',
};

const timelineAssetPath = (lesson: string, assetPath: string): string => {
  const prefix = `build/${lesson}/`;
  const relative = assetPath.startsWith(prefix)
    ? assetPath.slice(prefix.length)
    : assetPath;
  return stagingPath(lesson, relative);
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

const AssetFrame: React.FC<{
  lesson: string;
  shot: TimelineVideo;
}> = ({lesson, shot}) => {
  const src = staticFile(timelineAssetPath(lesson, shot.asset.path));
  if (shot.asset.kind === 'image') {
    const motion = shot.metadata?.legacy_motion as KenBurnsMotion | undefined;
    if (motion && motion.kind === 'ken_burns') {
      return (
        <MotionImage
          src={src}
          durationInFrames={shot.duration_frames}
          motion={motion}
        />
      );
    }
    return <Img src={src} style={videoStyle} />;
  }
  return <OffthreadVideo src={src} style={videoStyle} />;
};

const BaseVideo: React.FC<{lesson: string; shot: TimelineVideo}> = ({
  lesson,
  shot,
}) => (
  <Sequence
    from={shot.start_frame}
    durationInFrames={shot.duration_frames}
    name={`${shot.shot_id}:base`}
  >
    <AssetFrame lesson={lesson} shot={shot} />
  </Sequence>
);

const OverlayContent: React.FC<{
  lesson: string;
  shot: TimelineVideo;
}> = ({lesson, shot}) => {
  const presentation =
    ((shot.metadata?.legacy_presentation as Presentation | undefined) ??
      'cutaway') as Presentation;
  const src = staticFile(timelineAssetPath(lesson, shot.asset.path));

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
      style={{
        backgroundColor: presentation === 'cutaway' ? COLORS.paper : 'transparent',
      }}
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

const OverlayVideo: React.FC<{lesson: string; shot: TimelineVideo}> = ({
  lesson,
  shot,
}) => (
  <Sequence
    from={shot.start_frame}
    durationInFrames={shot.duration_frames}
    name={`${shot.shot_id}:overlay`}
  >
    <Fade durationInFrames={shot.duration_frames}>
      <OverlayContent lesson={lesson} shot={shot} />
    </Fade>
  </Sequence>
);

const TimelineAudioTrack: React.FC<{
  lesson: string;
  track: TimelineAudio;
}> = ({lesson, track}) => (
  <Sequence
    from={track.start_frame}
    durationInFrames={track.duration_frames}
    name={`${track.narration_id}:audio`}
  >
    <Audio
      src={staticFile(timelineAssetPath(lesson, track.asset.path))}
      volume={Math.min(1, Math.max(0, Math.pow(10, (track.gain_db ?? 0) / 20)))}
    />
  </Sequence>
);

const TimelineCaptions: React.FC<{cues: TimelineCue[]}> = ({cues}) => {
  const frame = useCurrentFrame();
  const cue = cues.find(
    (item) => frame >= item.start_frame && frame < item.end_frame,
  );
  if (!cue) return null;
  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 64}}
    >
      <div
        style={{
          background: 'rgba(255,255,255,0.92)',
          color: COLORS.text,
          fontFamily: FONTS.sans,
          fontSize: 36,
          lineHeight: 1.4,
          padding: '18px 28px',
          borderLeft: `4px solid ${COLORS.orange}`,
          maxWidth: '80%',
          textAlign: 'center',
          whiteSpace: 'pre-wrap',
        }}
      >
        {cue.text}
      </div>
    </AbsoluteFill>
  );
};

export const CourseTimeline: React.FC<TimelineSpec> = (props) => {
  const lesson = props.lesson_id;
  const base = (props.video ?? []).filter((shot) => shot.role === 'base');
  const overlays = (props.video ?? []).filter((shot) => shot.role === 'overlay');
  const annotations = ((props.metadata?.legacy_annotations ??
    props.metadata?.annotations ??
    null) as Annotation[] | null);
  const showCaptions = props.captions !== false;

  return (
    <AbsoluteFill style={{backgroundColor: COLORS.paper}}>
      {base.map((shot) => (
        <BaseVideo key={shot.shot_id} lesson={lesson} shot={shot} />
      ))}
      {overlays.map((shot) => (
        <OverlayVideo key={shot.shot_id} lesson={lesson} shot={shot} />
      ))}
      <Annotations annotations={annotations} />
      {showCaptions && props.subtitles?.length ? (
        <TimelineCaptions cues={props.subtitles} />
      ) : null}
      {(props.audio ?? []).map((track) => (
        <TimelineAudioTrack key={track.narration_id} lesson={lesson} track={track} />
      ))}
    </AbsoluteFill>
  );
};
