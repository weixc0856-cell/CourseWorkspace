import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const SANS_FAMILY = 'Noto Sans SC';

// Fontsource's Latin subset, copied verbatim from
// node_modules/@fontsource/noto-sans-sc/files/noto-sans-sc-latin-400-normal.woff2
const LATIN_UNICODE_RANGE =
  'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';

// CJK first, Latin second: the Latin face is scoped by unicode-range, so it
// wins for ASCII while the CJK face covers everything else.
loadFont({
  family: SANS_FAMILY,
  url: staticFile('fonts/noto-sans-sc-chinese-simplified-400-normal.woff2'),
  weight: '400',
  format: 'woff2',
});

loadFont({
  family: SANS_FAMILY,
  url: staticFile('fonts/noto-sans-sc-latin-400-normal.woff2'),
  weight: '400',
  format: 'woff2',
  unicodeRange: LATIN_UNICODE_RANGE,
});

// 600/700 are Latin-only subsets. Chinese text stays at 400 so a missing CJK
// bold face can never trigger a synthetic bold in production.
loadFont({
  family: SANS_FAMILY,
  url: staticFile('fonts/noto-sans-sc-latin-600-normal.woff2'),
  weight: '600',
  format: 'woff2',
  unicodeRange: LATIN_UNICODE_RANGE,
});

loadFont({
  family: SANS_FAMILY,
  url: staticFile('fonts/noto-sans-sc-latin-700-normal.woff2'),
  weight: '700',
  format: 'woff2',
  unicodeRange: LATIN_UNICODE_RANGE,
});
