export type ShortTheme = 'editorial_science' | 'deep_space' | 'engineering_studio';

export type CompareSide = {
  label: string;
  title: string;
  points?: string[];
  accent?: string;
};

export type SplitCompareProps = {
  left: CompareSide;
  right: CompareSide;
  verdict?: string;
};

export type PaperHighlightProps = {
  image: string;
  /** Normalised box on the image: 0-1 in both axes. */
  box: {x: number; y: number; w: number; h: number};
  label?: string;
  caption?: string;
  source?: string;
};

export type MetricBarProps = {
  title?: string;
  data: {label: string; value: number; display?: string; color?: string}[];
  max?: number;
  unit?: string;
  source?: string;
  note?: string;
};

export type FlowProps = {
  title?: string;
  steps: {label: string; detail?: string; accent?: string}[];
  direction?: 'horizontal' | 'vertical';
  footer?: string;
};

export type StatementProps = {
  kicker?: string;
  text: string;
  emphasis?: string;
  sub?: string;
  align?: 'left' | 'center';
  size?: 'hero' | 'large' | 'normal';
};

export type ScenePurpose =
  | 'explain'
  | 'demonstrate'
  | 'compare'
  | 'orient'
  | 'summarize'
  | 'emote';

export type SceneKind =
  | 'statement'
  | 'split_compare'
  | 'paper_highlight'
  | 'metric_bar'
  | 'simple_flow';

export type ShortScene =
  | {id: string; kind: 'statement'; duration_s: number; purpose: ScenePurpose; props: StatementProps}
  | {id: string; kind: 'split_compare'; duration_s: number; purpose: ScenePurpose; props: SplitCompareProps}
  | {id: string; kind: 'paper_highlight'; duration_s: number; purpose: ScenePurpose; props: PaperHighlightProps}
  | {id: string; kind: 'metric_bar'; duration_s: number; purpose: ScenePurpose; props: MetricBarProps}
  | {id: string; kind: 'simple_flow'; duration_s: number; purpose: ScenePurpose; props: FlowProps};

export type Caption = {
  start_s: number;
  end_s: number;
  en: string;
  zh?: string;
};

export type ShortStoryboardProps = {
  schema_version: 1;
  id: string;
  title: string;
  theme?: ShortTheme;
  aspect: '16:9' | '9:16' | '1:1';
  fps: number;
  audio?: string;
  scenes: ShortScene[];
  captions?: Caption[];
};
