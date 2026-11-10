/**
 * Props handed to every brand composition.
 *
 * CourseControl writes these into `build/<lesson>/brand/*.props.json`; the
 * fields are optional so a composition can be previewed in Remotion Studio
 * without a lesson. Text is never generated here: the brand layer renders what
 * the lesson plan supplies.
 */
export type BrandProps = {
  /** Segment length. Must stay inside the preset's min/max in brand.json. */
  durationInSeconds?: number;
  /** Course / episode title in the primary language. */
  title?: string;
  /** Secondary title (usually the other language). */
  subtitle?: string;
  /** Upper-case series label, e.g. `ENGINEERING COURSES`. */
  category?: string;
  /** Localised series label, e.g. `工程课程`. */
  categoryZh?: string;
  /** Series / textbook or playlist name. */
  series?: string;
  /** Episode number shown next to the series label. */
  episode?: string;
  /** Next lesson title for the course outro. */
  nextTitle?: string;
  /** ISO date for the news outro. Rendered verbatim; never invented. */
  date?: string;
  /** Draw the reserved YouTube end-screen area (preview only). */
  showReservedArea?: boolean;
};

export type BrandPreset = {
  composition: string;
  duration_s: number;
  min_s: number;
  max_s: number;
  aspect: 'landscape' | 'portrait';
};
