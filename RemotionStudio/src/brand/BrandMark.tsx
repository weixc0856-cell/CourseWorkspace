import React from 'react';
import {interpolate} from 'remotion';
import {BRAND} from './tokens';
import {FONTS} from '../styles/tokens';
import {TRACKING, TYPE} from './layout';

/**
 * The WAYNE mark: a graphite W with one orange current inside it.
 *
 * The W is a single polyline drawn with SVG `pathLength={1}`, so the reveal is
 * a pure dash-offset animation — no masks, no bitmaps, deterministic at any
 * fps. The accent is an inset line, never a filled block.
 */
export type BrandMarkProps = {
  width?: number;
  progress?: number;
  flow?: number;
  strokeWidth?: number;
  accent?: string;
  ink?: string;
};

const W_PATH = 'M24 44 L66 132 L120 68 L174 132 L216 44';
const CURRENT_PATH = 'M75 121 L113 77';

export const BrandMark: React.FC<BrandMarkProps> = ({
  width = 320,
  progress = 1,
  flow = 0,
  strokeWidth = 18,
  accent = BRAND.accent,
  ink = BRAND.ink,
}) => {
  const clamped = Math.min(1, Math.max(0, progress));
  const current = Math.min(1, Math.max(0, (clamped - 0.7) / 0.3));

  return (
    <svg
      width={width}
      height={(width * 168) / 240}
      viewBox="0 0 240 168"
      fill="none"
      aria-hidden
    >
      {[36, 84, 132].map((y, index) => (
        <line
          key={y}
          x1={-120 + 120 * Math.min(1, Math.max(0, flow * 3 - index * 0.6))}
          y1={y}
          x2={2}
          y2={y}
          stroke={BRAND.hairline}
          strokeWidth={2}
        />
      ))}
      <path
        d={W_PATH}
        pathLength={1}
        stroke={ink}
        strokeWidth={strokeWidth}
        strokeLinecap="butt"
        strokeLinejoin="miter"
        strokeDasharray={1}
        strokeDashoffset={1 - clamped}
      />
      <path
        d={CURRENT_PATH}
        pathLength={1}
        stroke={accent}
        strokeWidth={strokeWidth * 0.55}
        strokeLinecap="round"
        strokeDasharray={1}
        strokeDashoffset={1 - current}
      />
    </svg>
  );
};

/**
 * The brand lockup.
 *
 * `display` is the title-page size: the mark shares a baseline with a 168 px
 * wordmark and the tagline sits underneath. `compact` is the masthead used on
 * endings: 34 px mark, 28 px wordmark, 12 px tagline, on one line.
 */
export const Lockup: React.FC<{
  variant?: 'display' | 'compact';
  progress?: number;
  taglineProgress?: number;
  track?: number;
  markProgress?: number;
  wordSize?: number;
}> = ({
  variant = 'compact',
  progress = 1,
  taglineProgress = 1,
  track = 1,
  markProgress = 1,
  wordSize,
}) => {
  const display = variant === 'display';
  const size = wordSize ?? (display ? TYPE.display : 28);
  const markWidth = display ? Math.round(size * 0.89) : 40;
  const wordTracking = display
    ? interpolate(track, [0, 1], [0.06, -0.05])
    : TRACKING.title;

  // Align the mark's centre to the wordmark's cap centre. The line box is not
  // the same as the glyph box (display leading is 0.9), so the offset mixes the
  // line-box centre, half the mark height and a small optical correction.
  const lineHeight = display ? 0.9 : 1;
  const markOffset = size * lineHeight * 0.5 - markWidth * 0.35 + size * 0.04;

  return (
    <div style={{display: 'flex', alignItems: 'flex-start', gap: display ? 34 : 14}}>
      <div style={{marginTop: markOffset}}>
        <BrandMark
          width={markWidth}
          progress={markProgress}
          strokeWidth={display ? 20 : 26}
        />
      </div>
      <div>
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: size,
            fontWeight: 700,
            lineHeight: display ? 0.9 : 1,
            letterSpacing: `${wordTracking}em`,
            color: BRAND.ink,
            opacity: progress,
          }}
        >
          {BRAND.identity.name}
        </div>
        <div
          style={{
            marginTop: display ? 22 : 7,
            fontFamily: FONTS.sans,
            fontSize: display ? 20 : 12,
            fontWeight: 600,
            letterSpacing: '0.22em',
            textTransform: 'uppercase',
            color: BRAND.muted,
            opacity: taglineProgress,
            whiteSpace: 'nowrap',
          }}
        >
          {BRAND.identity.tagline}
        </div>
      </div>
    </div>
  );
};

/**
 * Centred lockup for end cards and signatures.
 *
 * The mark and the wordmark form one row centred in the frame; the tagline is
 * centred against that whole row, not against the wordmark. Left-aligning the
 * tagline under WAYNE shifted the visual axis by ~40 px while the thanks copy
 * stayed on the frame centre — the exact defect the end card must not have.
 */
export const CenteredLockup: React.FC<{
  wordSize?: number;
  progress?: number;
  taglineProgress?: number;
  markProgress?: number;
}> = ({
  wordSize = 120,
  progress = 1,
  taglineProgress = 1,
  markProgress = 1,
}) => {
  const markWidth = Math.round(wordSize * 0.89);
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 28,
          opacity: progress,
        }}
      >
        <BrandMark width={markWidth} progress={markProgress} strokeWidth={20} />
        <div
          style={{
            fontFamily: FONTS.sans,
            fontSize: wordSize,
            fontWeight: 700,
            lineHeight: 1,
            letterSpacing: '-0.05em',
            color: BRAND.ink,
            whiteSpace: 'nowrap',
          }}
        >
          {BRAND.identity.name}
        </div>
      </div>
      <div
        style={{
          marginTop: 22,
          fontFamily: FONTS.sans,
          fontSize: 20,
          fontWeight: 600,
          letterSpacing: '0.22em',
          textTransform: 'uppercase',
          color: BRAND.muted,
          opacity: taglineProgress,
          textAlign: 'center',
          whiteSpace: 'nowrap',
          // letter-spacing adds a trailing gap after the last glyph; cancel it
          // so the ink box, not the padded box, sits on the centre line.
          marginRight: '-0.22em',
        }}
      >
        {BRAND.identity.tagline}
      </div>
    </div>
  );
};

/** Episode number in accent + category label, the brand's only two-tone line. */
export const Eyebrow: React.FC<{
  category?: string;
  categoryZh?: string;
  episode?: string;
  progress?: number;
}> = ({category, categoryZh, episode, progress = 1}) => {
  if (!category && !categoryZh) return null;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: 18,
        fontFamily: FONTS.sans,
        fontSize: TYPE.label,
        fontWeight: 600,
        letterSpacing: TRACKING.label,
        textTransform: 'uppercase',
        color: BRAND.muted,
        opacity: progress,
      }}
    >
      {episode ? <span style={{color: BRAND.accent}}>{episode}</span> : null}
      <span>{category}</span>
      {categoryZh ? (
        <span style={{color: BRAND.muted, letterSpacing: '0.08em'}}>{categoryZh}</span>
      ) : null}
    </div>
  );
};

/** Thin accent rule used above a title or a next-lesson block. */
export const AccentRule: React.FC<{progress?: number; width?: number; height?: number}> = ({
  progress = 1,
  width = 64,
  height = 3,
}) => (
  <div
    style={{
      width: width * progress,
      height,
      backgroundColor: BRAND.accent,
    }}
  />
);

export const framesFor = (seconds: number, fps: number): number =>
  Math.max(1, Math.round(seconds * fps));

export const progressBetween = (
  frame: number,
  start: number,
  end: number,
): number =>
  interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
