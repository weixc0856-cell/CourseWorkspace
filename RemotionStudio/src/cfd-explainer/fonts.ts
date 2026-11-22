// Font loading for the CFD explainer composition.
//
// The composition is rendered with --public-dir pointed at the content-root
// anim directory (where the frame sequences live), so it cannot use the
// project's src/fonts/loadFonts.ts paths. episode_build.py syncs the same
// bundled OFL files into <anim>/fonts/, and this loader mirrors the repo's
// unicode-range discipline: CJK first at 400, Latin subsets scoped so ASCII
// never falls back to a system face.
import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

export const SANS_FAMILY = 'Noto Sans SC';
export const DISPLAY_FAMILY = 'Jost';

const LATIN_UNICODE_RANGE =
  'U+0000-00FF,U+0131,U+0152,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';

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
loadFont({
  family: DISPLAY_FAMILY,
  url: staticFile('fonts/jost-latin-200-normal.woff2'),
  weight: '200',
  format: 'woff2',
});
loadFont({
  family: DISPLAY_FAMILY,
  url: staticFile('fonts/jost-latin-300-normal.woff2'),
  weight: '300',
  format: 'woff2',
});
loadFont({
  family: DISPLAY_FAMILY,
  url: staticFile('fonts/jost-latin-700-normal.woff2'),
  weight: '700',
  format: 'woff2',
});
