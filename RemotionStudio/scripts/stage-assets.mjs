import {cp, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, '..');
const workspaceRoot = path.resolve(projectRoot, '..');

const parseArgs = (argv) => {
  const result = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) continue;
    result[token.slice(2)] = argv[i + 1];
    i += 1;
  }
  return result;
};

const args = parseArgs(process.argv.slice(2));
const timelinePath = args.timeline ? path.resolve(args.timeline) : null;
const timeline = timelinePath ? JSON.parse(await readFile(timelinePath, 'utf8')) : null;
const lesson = args.lesson ?? timeline?.lesson_id;
if (!lesson) {
  console.error('ERROR: --lesson <slug> or --timeline <timeline.spec.json> is required');
  process.exit(2);
}

const buildRoot = args['build-root']
  ? path.resolve(args['build-root'])
  : path.join(workspaceRoot, 'build', lesson);
const shotsPath = timeline ? null : path.resolve(args.shots ?? path.join(buildRoot, 'shots.json'));
const stagingDir = path.join(projectRoot, 'public', 'staging', lesson);

let sources;
if (timeline) {
  // Timeline assets are workspace-relative (`build/<lesson>/...`), but a
  // build may live under a different root (fixtures, isolated production).
  // Resolve against the workspace and make it relative to the actual root.
  const toBuildRelative = (assetPath) => {
    if (!assetPath.startsWith('build/')) return assetPath;
    const absolute = path.resolve(workspaceRoot, assetPath);
    const relative = path.relative(buildRoot, absolute);
    return relative.startsWith('..') ? assetPath : relative;
  };
  sources = new Set([
    ...(timeline.video ?? []).map((item) => toBuildRelative(item.asset.path)),
    ...(timeline.audio ?? []).map((item) => toBuildRelative(item.asset.path)),
  ]);
} else {
  const shots = JSON.parse(await readFile(shotsPath, 'utf8'));
  sources = new Set(shots.shots.map((shot) => shot.source));
  if (shots.narration?.path) sources.add(shots.narration.path);
  if (shots.subtitles?.path) sources.add(shots.subtitles.path);
}

await rm(stagingDir, {recursive: true, force: true});
await mkdir(stagingDir, {recursive: true});

const copied = [];
for (const source of sources) {
  const from = path.join(buildRoot, source);
  const to = path.join(stagingDir, source);
  try {
    await mkdir(path.dirname(to), {recursive: true});
    await cp(from, to);
    copied.push(source);
  } catch (error) {
    console.error(`ERROR: cannot stage ${from}: ${error.message}`);
    process.exit(1);
  }
}

await writeFile(
  path.join(stagingDir, 'staging-manifest.json'),
  JSON.stringify(
    {
      lesson,
      mode: timeline ? 'timeline' : 'legacy',
      shots: shotsPath,
      timeline: timelinePath,
      files: copied,
      staged_at: new Date().toISOString(),
    },
    null,
    2,
  ) + '\n',
  'utf8',
);

console.log(`STAGED ${copied.length} files -> ${stagingDir}`);
for (const file of copied) console.log(`  ${file}`);
