import {cp, mkdir, readFile, rm, writeFile, readdir, stat} from 'node:fs/promises';
import {existsSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {contentRoot} from './content-root.mjs';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, '..');

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

// Every source path is either content-root relative or absolute. The default
// build root follows the content root; the repository is never a fallback.
const contentRootPath = contentRoot();
const buildRoot = args['build-root']
  ? path.resolve(args['build-root'])
  : path.join(contentRootPath, 'build', lesson);
const shotsPath = timeline ? null : path.resolve(args.shots ?? path.join(buildRoot, 'shots.json'));
const manifestPath = args.manifest ? path.resolve(args.manifest) : null;
const stagingDir = path.join(projectRoot, 'public', 'staging', lesson);
const WARN_BYTES = 512 * 1024 * 1024;
const LIMIT_BYTES = 2 * 1024 * 1024 * 1024;

const toBuildRelative = (assetPath) => {
  // The content root can sit outside the workspace, in which case the
  // timeline carries an absolute path; make it build-relative when it falls
  // under this build, otherwise leave it absolute for the copy step.
  if (path.isAbsolute(assetPath)) {
    const relative = path.relative(buildRoot, assetPath);
    return relative.startsWith('..') ? assetPath : relative;
  }
  if (!assetPath.startsWith('build/')) return assetPath;
  const absolute = path.resolve(contentRootPath, assetPath);
  const relative = path.relative(buildRoot, absolute);
  return relative.startsWith('..') ? assetPath : relative;
};

let sources = new Set();
let manifestFiles = null;
if (manifestPath) {
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  manifestFiles = manifest.files ?? [];
} else if (timeline) {
  // Timeline assets are content-root relative (`build/<lesson>/...`), but a
  // build may live under a different root (fixtures, isolated production).
  sources = new Set([
    ...(timeline.video ?? []).map((item) => toBuildRelative(item.asset.path)),
    ...(timeline.audio ?? []).map((item) => toBuildRelative(item.asset.path)),
  ]);
} else {
  if (!existsSync(shotsPath)) {
    console.error(`ERROR: neither --manifest nor shots.json found at ${shotsPath}`);
    process.exit(2);
  }
  const shots = JSON.parse(await readFile(shotsPath, 'utf8'));
  sources = new Set(shots.shots.map((shot) => shot.source));
  if (shots.narration?.path) sources.add(shots.narration.path);
  if (shots.subtitles?.path) sources.add(shots.subtitles.path);
}

const stagingRoot = path.join(projectRoot, 'public', 'staging');
if (args.clean === 'true' || args.clean === '') {
  await rm(stagingRoot, {recursive: true, force: true});
  console.log(`CLEANED ${stagingRoot}`);
}
await rm(stagingDir, {recursive: true, force: true});
await mkdir(stagingDir, {recursive: true});

const pairs = [];
if (manifestFiles) {
  for (const item of manifestFiles) {
    pairs.push({
      from: path.resolve(contentRootPath, item.from),
      to: path.join(stagingDir, item.to),
      label: item.from,
    });
  }
} else {
  for (const source of sources) {
    pairs.push({
      from: path.isAbsolute(source) ? source : path.join(buildRoot, source),
      to: path.join(stagingDir, source),
      label: source,
    });
  }
}

const copied = [];
for (const pair of pairs) {
  try {
    await mkdir(path.dirname(pair.to), {recursive: true});
    await cp(pair.from, pair.to);
    copied.push(pair.label);
  } catch (error) {
    console.error(`ERROR: cannot stage ${pair.from}: ${error.message}`);
    process.exit(1);
  }
}

const dirBytes = async (dir) => {
  let total = 0;
  for (const entry of await readdir(dir, {withFileTypes: true})) {
    const full = path.join(dir, entry.name);
    total += entry.isDirectory() ? await dirBytes(full) : (await stat(full)).size;
  }
  return total;
};

await writeFile(
  path.join(stagingDir, 'staging-manifest.json'),
  JSON.stringify(
    {
      lesson,
      mode: manifestPath ? 'manifest' : timeline ? 'timeline' : 'legacy',
      shots: shotsPath,
      timeline: timelinePath,
      manifest: manifestPath,
      files: copied,
      staged_at: new Date().toISOString(),
    },
    null,
    2,
  ) + '\n',
  'utf8',
);

// Staging keeps only the lesson being built. Other slugs are copies that can be
// staged again; leaving them behind is how the folder grew to 300+ MB.
if (args['keep-others'] !== 'true') {
  for (const entry of await readdir(stagingRoot, {withFileTypes: true})) {
    if (!entry.isDirectory() || entry.name === lesson) continue;
    await rm(path.join(stagingRoot, entry.name), {recursive: true, force: true});
    console.log(`PRUNED stale staging: ${entry.name}`);
  }
}

const sizes = [];
for (const entry of await readdir(stagingRoot, {withFileTypes: true})) {
  if (entry.isDirectory()) {
    sizes.push([entry.name, await dirBytes(path.join(stagingRoot, entry.name))]);
  }
}
sizes.sort((a, b) => b[1] - a[1]);

const used = await dirBytes(stagingRoot);
const mb = (bytes) => (bytes / (1024 * 1024)).toFixed(1);
console.log(`STAGED ${copied.length} files -> ${stagingDir}`);
for (const file of copied) console.log(`  ${file}`);
for (const [slug, size] of sizes.slice(0, 5)) console.log(`STAGING SLUG ${slug} ${mb(size)} MB`);
console.log(`STAGING ${mb(used)} MB of ${mb(LIMIT_BYTES)} MB (warn at ${mb(WARN_BYTES)} MB)`);
if (used > LIMIT_BYTES) {
  console.error('ERROR: staging exceeds the limit; rerun with --clean true');
  process.exit(1);
}
if (used > WARN_BYTES) {
  console.warn('WARNING: staging is above the warning line');
}
