import type {CSSProperties} from 'react';
import tokens from '../../../shared/design-tokens/tokens.json';
import spec from '../../../shared/design-tokens/brand.json';

export const COLORS = tokens.colors;
export const FONTS = tokens.fonts;

/**
 * Brand layer tokens.
 *
 * The palette is *not* redefined here. Brand colour roles map onto the course
 * design tokens (`shared/design-tokens/tokens.json`), so the intro, the slides
 * and the semantic scene colours stay one system (FR-31). A second set of hex
 * values would silently fork the palette the moment one side is edited.
 */
export const BRAND = {
  background: COLORS.paper,
  surface: COLORS.surface,
  ink: COLORS.ink,
  body: COLORS.text,
  muted: COLORS.muted,
  accent: COLORS.orange,
  accentSoft: COLORS.orangeSoft,
  hairline: COLORS.border,
  onAccent: COLORS.white,
  identity: spec.identity,
  canvas: spec.canvas,
  contentKinds: spec.content_kinds,
  presets: spec.presets,
  rules: spec.rules,
} as const;

export type ContentKind = keyof typeof spec.content_kinds;
export type PresetId = keyof typeof spec.presets;

export const LABEL_FONT = FONTS.sans;

export const labelStyle: CSSProperties = {
  fontFamily: LABEL_FONT,
  fontSize: 22,
  fontWeight: 600,
  letterSpacing: '0.22em',
  textTransform: 'uppercase',
};
