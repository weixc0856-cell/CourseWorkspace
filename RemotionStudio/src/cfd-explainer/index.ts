import './fonts';
import {registerRoot} from 'remotion';
import {CfdRoot} from './Root';

// Separate entry on purpose: src/index.ts and the production Root stay
// untouched; this composition is rendered by name/path from episode_build.py.
registerRoot(CfdRoot);
