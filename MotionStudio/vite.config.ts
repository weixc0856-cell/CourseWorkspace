import {defineConfig} from 'vite';
import motionCanvas from '@motion-canvas/vite-plugin';
import ffmpeg from '@motion-canvas/ffmpeg';

export default defineConfig({
  plugins: [motionCanvas(), ffmpeg()],
  // Headless capture does not need HMR; disabling it also stops scene .meta writes.
  server: process.env.MOTION_CANVAS_HEADLESS === '1' ? {hmr: false} : undefined,
});
