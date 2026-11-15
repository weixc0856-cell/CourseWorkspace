// Copy one lesson's media from the content root into public/staging/<slug>/.
//
// Usage:
//   node scripts/stage-media.mjs <slug>           fresh stage for one lesson
//   node scripts/stage-media.mjs <slug> --clean   wipe all staging first
//
// Manifest: RemotionStudio/stage/<slug>.json  { "files": [{ "from": "...", "to": "..." }] }
// "from" is relative to the content root, "to" relative to the staging folder.
// public/staging/ is gitignored: the bytes never enter the repository.
//
// Staging is a cache, not storage. Each run replaces the slug folder, prints
// the total size and fails when staging grows past the limit.

import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
import { contentRoot, workspace } from './content-root.mjs';

const args = process.argv.slice(2);
const clean = args.includes('--clean');
const slug = args.find((value) => !value.startsWith('--'));
if (!slug) {
  console.error('usage: node scripts/stage-media.mjs <slug> [--clean]');
  process.exit(2);
}

const stagingRoot = resolve(workspace, 'RemotionStudio', 'public', 'staging');
const manifestPath = resolve(workspace, 'RemotionStudio', 'stage', slug + '.json');
if (!existsSync(manifestPath)) {
  console.error('manifest not found: ' + manifestPath);
  process.exit(2);
}

function dirBytes(dir) {
  if (!existsSync(dir)) return 0;
  let total = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = resolve(dir, entry.name);
    total += entry.isDirectory() ? dirBytes(full) : statSync(full).size;
  }
  return total;
}

function mb(bytes) {
  return (bytes / (1024 * 1024)).toFixed(1);
}

const LIMIT = 2 * 1024 * 1024 * 1024;
if (clean) {
  rmSync(stagingRoot, { recursive: true, force: true });
  console.log('cleaned ' + stagingRoot);
}

const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
const root = contentRoot();
const targetDir = resolve(stagingRoot, slug);
rmSync(targetDir, { recursive: true, force: true });
mkdirSync(targetDir, { recursive: true });

let copied = 0;
for (const item of manifest.files || []) {
  const source = resolve(root, item.from);
  if (!existsSync(source)) {
    console.error('missing source: ' + source);
    process.exit(1);
  }
  const target = resolve(targetDir, item.to);
  mkdirSync(resolve(target, '..'), { recursive: true });
  copyFileSync(source, target);
  console.log('staged ' + item.from + ' -> public/staging/' + slug + '/' + item.to);
  copied += 1;
}

const used = dirBytes(stagingRoot);
console.log('staged ' + copied + ' file(s) for ' + slug);
console.log('staging: ' + mb(used) + ' MB of ' + mb(LIMIT) + ' MB');
if (used > LIMIT) {
  console.error('staging exceeds the limit; run with --clean to drop older slugs');
  process.exit(1);
}
