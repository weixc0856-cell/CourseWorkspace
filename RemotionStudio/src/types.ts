export type TimelineRole = 'base' | 'overlay';
export type Presentation = 'cutaway' | 'picture_in_picture' | 'transparent_overlay';
export type ShotKind = 'slide' | 'animation' | 'recording';

export type AnnotationColor = 'text' | 'muted' | 'orange' | 'white';

export type TextAnnotation = {
  id: string;
  kind: 'text';
  text: string;
  start_s: number;
  duration_s: number;
  position: [number, number];
  size: number;
  align: 'left' | 'center' | 'right';
  color: AnnotationColor;
  background: boolean;
};

export type LegendStop = [number, [number, number, number]];

export type LegendAnnotation = {
  id: string;
  kind: 'legend';
  start_s: number;
  duration_s: number;
  position: [number, number];
  colormap: string;
  min_value: number;
  max_value: number;
  units: string;
  stops: LegendStop[];
  bar_height: number;
  bar_width: number;
  label_size: number;
};

export type Annotation = TextAnnotation | LegendAnnotation;

export type Shot = {
  id: string;
  kind: ShotKind;
  slide?: number;
  engine?: string | null;
  source: string;
  start_s: number;
  duration_s: number;
  timeline_role: TimelineRole;
  presentation?: Presentation | null;
};

export type ShotsFile = {
  schema_version: number;
  lesson: string;
  generated_at?: string;
  timeline: {
    fps: number;
    resolution: [number, number];
    total_duration_s: number;
  };
  shots: Shot[];
  annotations?: Annotation[];
  narration?: {path: string; duration_s: number} | null;
  subtitles?: {path: string; cues: number} | null;
  captions?: boolean;
};

export type RationalFPS = {
  fps_num: number;
  fps_den: number;
};

export type TimelineAsset = {
  path: string;
  sha256?: string;
  bytes?: number;
  kind: string;
  origin?: string;
  version?: string | null;
};

export type TimelineVideo = {
  shot_id: string;
  start_frame: number;
  duration_frames: number;
  role: 'base' | 'overlay';
  z?: number;
  asset: TimelineAsset;
  track?: string | null;
  metadata?: Record<string, unknown> | null;
};

export type TimelineAudio = {
  narration_id: string;
  start_frame: number;
  duration_frames: number;
  asset: TimelineAsset;
  gain_db?: number;
};

export type TimelineCue = {
  index: number;
  start_frame: number;
  end_frame: number;
  text: string;
};

export type TimelineSpec = {
  schema_version: number;
  kind: 'timeline_spec';
  lesson_id: string;
  fps: RationalFPS;
  width: number;
  height: number;
  total_frames: number;
  video: TimelineVideo[];
  audio: TimelineAudio[];
  subtitles: TimelineCue[];
  sync?: {
    audio_tolerance_frames?: number;
    subtitle_tolerance_ms?: number;
    allow_gap_frames?: number;
  };
  metadata?: {
    annotations?: Annotation[];
    legacy_annotations?: Annotation[];
    [key: string]: unknown;
  } | null;
  captions?: boolean;
};
