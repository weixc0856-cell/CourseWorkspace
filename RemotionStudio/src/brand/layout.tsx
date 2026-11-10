import React from 'react';
import type {CSSProperties} from 'react';
import {BRAND} from './tokens';
import {FONTS} from '../styles/tokens';

/**
 * One geometry for every brand frame.
 *
 * A 12-column grid with a 96 px margin. Type sits on a small fixed scale:
 * negative tracking on display sizes, wide tracking on micro labels. Nothing
 * is centred by default — asymmetry is what makes a title page read as
 * editorial instead of as a logo sting.
 */
export const CANVAS = {
  width: 1920,
  height: 1080,
  margin: 96,
  gutter: 24,
  columns: 12,
} as const;

export const CONTENT_WIDTH = CANVAS.width - CANVAS.margin * 2;
export const COLUMN_WIDTH =
  (CONTENT_WIDTH - CANVAS.gutter * (CANVAS.columns - 1)) / CANVAS.columns;

/** Column span helper: (start 1-based, span) -> left offset and width in px. */
export const col = (start: number, span: number) => ({
  left: CANVAS.margin + (start - 1) * (COLUMN_WIDTH + CANVAS.gutter),
  width: COLUMN_WIDTH * span + CANVAS.gutter * (span - 1),
});

export const TYPE = {
  display: 168,
  title: 72,
  heading: 44,
  body: 30,
  label: 18,
  micro: 13,
} as const;

export const TRACKING = {
  display: '-0.05em',
  title: '-0.025em',
  heading: '-0.015em',
  body: '0em',
  label: '0.2em',
  micro: '0.16em',
} as const;

export const LEADING = {
  display: 0.9,
  title: 1.05,
  heading: 1.2,
  body: 1.5,
} as const;

/**
 * Approximate visual width in em: a CJK glyph is 1 em, Latin averages 0.55.
 * Used to pick a display size that keeps a dynamic title on one line.
 */
const isCjk = (code: number): boolean =>
  (code >= 0x3000 && code <= 0x9fff) || (code >= 0xff00 && code <= 0xffef);

export const textUnits = (text: string): number =>
  [...text].reduce(
    (total, char) => total + (isCjk(char.charCodeAt(0)) ? 1 : 0.55),
    0,
  );

export const fitFontSize = (
  text: string,
  width: number,
  sizes: number[],
): number => {
  const units = textUnits(text);
  return sizes.find((size) => units * size <= width) ?? sizes[sizes.length - 1];
};

export const displayStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.display,
  fontWeight: 700,
  lineHeight: LEADING.display,
  letterSpacing: TRACKING.display,
  color: BRAND.ink,
};

export const titleStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.title,
  fontWeight: 700,
  lineHeight: LEADING.title,
  letterSpacing: TRACKING.title,
  color: BRAND.ink,
};

export const headingStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.heading,
  fontWeight: 600,
  lineHeight: LEADING.heading,
  letterSpacing: TRACKING.heading,
  color: BRAND.ink,
};

export const bodyStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.body,
  fontWeight: 400,
  lineHeight: LEADING.body,
  color: BRAND.body,
};

export const labelStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.label,
  fontWeight: 600,
  letterSpacing: TRACKING.label,
  textTransform: 'uppercase',
  color: BRAND.muted,
};

export const microStyle: CSSProperties = {
  fontFamily: FONTS.sans,
  fontSize: TYPE.micro,
  fontWeight: 600,
  letterSpacing: TRACKING.micro,
  textTransform: 'uppercase',
  color: BRAND.muted,
};

/** A one-pixel rule. The only structural decoration the brand layer uses. */
export const Hairline: React.FC<{
  top?: number;
  left?: number;
  width?: number | string;
  color?: string;
  opacity?: number;
}> = ({
  top = 0,
  left = CANVAS.margin,
  width = CONTENT_WIDTH,
  color = BRAND.hairline,
  opacity = 1,
}) => (
  <div
    style={{
      position: 'absolute',
      top,
      left,
      width,
      height: 1,
      backgroundColor: color,
      opacity,
    }}
  />
);
