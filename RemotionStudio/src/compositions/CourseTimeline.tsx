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
import {AgingHud, AgingHudOverlay} from '../overlays/AgingHud';
import {COLORS, FONTS} from '../styles/tokens';
import {
  Annotation,
  Presentation,
  TimelineAudio,
  TimelineCue,
  TimelineSpec,
  TimelineVideo,
  Transition,
  TransitionKind,
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

const transitionOf = (
  shot: TimelineVideo,
  fallback: TransitionKind,
): Transition => {
  const raw = shot.metadata?.legacy_transition as Partial<Transition> | undefined;
  return {in: raw?.in ?? fallback, out: raw?.out ?? fallback};
};

const TransitionWrap: React.FC<{
  durationInFrames: number;
  transition: Transition;
  children: React.ReactNode;
}> = ({durationInFrames, transition, children}) => {
  const frame = useCurrentFrame();
  if (transition.in === 'hard_cut' && transition.out === 'hard_cut') {
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }
  const fade = Math.min(12, Math.max(1, Math.floor(durationInFrames / 3)));
  const fadeIn = transition.in === 'hard_cut' ? 0 : fade;
  const fadeOut = transition.out === 'hard_cut' ? 0 : fade;
  const opacity = interpolate(
    frame,
    [0, Math.max(1, fadeIn), Math.max(1, durationInFrames - fadeOut), durationInFrames],
    [fadeIn ? 0 : 1, 1, 1, fadeOut ? 0 : 1],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'},
  );
  const wipe =
    transition.in === 'wipe'
      ? interpolate(frame, [0, Math.max(1, fadeIn)], [0, 100], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        })
      : 100;
  return (
    <AbsoluteFill
      style={{
        opacity,
        clipPath:
          transition.in === 'wipe' ? `inset(0 ${100 - wipe}% 0 0)` : undefined,
      }}
    >
      {children}
    </AbsoluteFill>
  );
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
    <TransitionWrap
      durationInFrames={shot.duration_frames}
      transition={transitionOf(shot, 'hard_cut')}
    >
      <AssetFrame lesson={lesson} shot={shot} />
    </TransitionWrap>
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
    <TransitionWrap
      durationInFrames={shot.duration_frames}
      transition={transitionOf(shot, 'fade')}
    >
      <OverlayContent lesson={lesson} shot={shot} />
    </TransitionWrap>
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

type WordCaption = {start_frame: number; end_frame: number; text: string};
type WordCaptionsData = {position: 'bottom' | 'low_center'; words: WordCaption[]};

const WordCaptions: React.FC<{data: WordCaptionsData}> = ({data}) => {
  const frame = useCurrentFrame();
  const index = data.words.findIndex(
    (word) => frame >= word.start_frame && frame < word.end_frame,
  );
  if (index < 0) return null;
  const current = data.words[index];
  const tail = data.words
    .slice(index + 1, index + 9)
    .map((word) => word.text)
    .join('');
  const lowCenter = data.position === 'low_center';
  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: lowCenter ? 300 : 90,
        paddingLeft: 120,
        paddingRight: 120,
      }}
    >
      <div
        style={{
          background: 'rgba(246,241,231,0.82)',
          borderRadius: 18,
          padding: '18px 34px',
          maxWidth: '90%',
          textAlign: 'center',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
        }}
      >
        <span
          style={{
            color: COLORS.orange,
            fontFamily: FONTS.sans,
            fontSize: 64,
            fontWeight: 700,
          }}
        >
          {current.text}
        </span>
        <span
          style={{
            color: COLORS.text,
            fontFamily: FONTS.sans,
            fontSize: 54,
            opacity: 0.45,
          }}
        >
          {tail}
        </span>
      </div>
    </AbsoluteFill>
  );
};

const TimelineCaptions: React.FC<{cues: TimelineCue[]}> = ({cues}) => {
  const frame = useCurrentFrame();
  const cue = cues.find(
    (item) => frame >= item.start_frame && frame < item.end_frame,
  );
  if (!cue) return null;
  return (
    <AbsoluteFill
      style={{justifyContent: 'flex-end', alignItems: 'center', paddingBottom: 120}}
    >
      <div
        style={{
          background: 'rgba(246,241,231,0.94)',
          color: COLORS.text,
          fontFamily: FONTS.sans,
          fontSize: 44,
          lineHeight: 1.35,
          padding: '20px 34px',
          borderLeft: `3px solid ${COLORS.orange}`,
          borderRadius: 8,
          maxWidth: '84%',
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
  const sceneOverlay = props.metadata?.overlay as AgingHudOverlay | undefined;
  const wordCaptions = props.metadata?.word_captions as WordCaptionsData | undefined;
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
      {sceneOverlay?.kind === 'aging_hud' ? (
        <AgingHud overlay={sceneOverlay} />
      ) : null}
      {showCaptions && wordCaptions ? (
        <WordCaptions data={wordCaptions} />
      ) : showCaptions && props.subtitles?.length ? (
        <TimelineCaptions cues={props.subtitles} />
      ) : null}
      {(props.audio ?? []).map((track) => (
        <TimelineAudioTrack key={track.narration_id} lesson={lesson} track={track} />
      ))}
    </AbsoluteFill>
  );
};
