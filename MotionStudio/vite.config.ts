import {defineConfig} from 'vite';
import motionCanvas from '@motion-canvas/vite-plugin';
import ffmpeg from '@motion-canvas/ffmpeg';
import {fileURLToPath} from 'node:url';
// @ts-expect-error plain .mjs shared resolver, no type declarations
import {contentRoot} from '../RemotionStudio/scripts/content-root.mjs';

const repoRoot = fileURLToPath(new URL('..', import.meta.url));
const content = contentRoot();

// Scenes reference course media as /scenes/<slug>/... (files next to the scene
// source) and /lessons/<slug>/assets/... (lesson assets in the content root).
// Neither prefix exists on disk under the vite root, so map them onto paths
// vite can serve. Junctioned scene files realpath into the content root, which
// fs.allow must therefore include.
function courseMedia() {
  return {
    name: 'course-media',
    configureServer(server: {middlewares: {use: (fn: Function) => void}}) {
      server.middlewares.use(
        (req: {url?: string}, _res: unknown, next: () => void) => {
          if (req.url?.startsWith('/scenes/')) {
            req.url = '/src' + req.url;
          } else if (req.url?.startsWith('/lessons/')) {
            req.url = '/@fs/' + content.replace(/\\/g, '/') + req.url;
          }
          next();
        },
      );
    },
  };
}

export default defineConfig({
  plugins: [motionCanvas(), ffmpeg(), courseMedia()],
  server: {
    fs: {allow: [repoRoot, content]},
    // Headless capture does not need HMR; disabling it also stops scene .meta writes.
    ...(process.env.MOTION_CANVAS_HEADLESS === '1' ? {hmr: false as const} : {}),
  },
});