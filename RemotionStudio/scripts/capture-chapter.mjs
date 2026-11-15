// Capture chapter stills into the content root.
//
// Usage: node scripts/capture-chapter.mjs [frame ...]
// Default frames: 150 750 3000 4050. Output: <content_root>/build/t1-01-chapter/frames/
// The still command never writes into the repository; content-root.mjs throws
// rather than fall back, so a missing config stops the run.

import { spawnSync } from 'node:child_process';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { contentPath, workspace } from './content-root.mjs';

const frames = process.argv.slice(2).filter((value) => !value.startsWith('--'));
const list = frames.length ? frames : ['150', '750', '3000', '4050'];
const outDir = contentPath('build', 't1-01-chapter', 'frames');
mkdirSync(outDir, { recursive: true });
const studio = resolve(workspace, 'RemotionStudio');

for (const frame of list) {
  const out = resolve(outDir, 'chapter-' + frame + '.png');
  const run = spawnSync(
    'npx',
    ['remotion', 'still', 'src/chapter/index.ts', 'Chapter', frame, out],
    { cwd: studio, stdio: 'inherit', shell: true },
  );
  if (run.status !== 0) process.exit(run.status || 1);
  console.log('wrote ' + out);
}
