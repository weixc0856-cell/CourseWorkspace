export type TimelineRole = 'base' | 'overlay';
export type Presentation = 'cutaway' | 'picture_in_picture' | 'transparent_overlay';
export type ShotKind = 'slide' | 'animation' | 'recording';

export type AnnotationColor = 'text' | 'muted' | 'orange' | 'white';

export type Annotation = {
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
};
