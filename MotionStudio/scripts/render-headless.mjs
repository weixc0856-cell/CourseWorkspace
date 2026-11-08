#!/usr/bin/env node
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {mkdir, readFile, readdir, rm, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {fileURLToPath, pathToFileURL} from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(scriptDir, '..');
const workspaceRoot = path.resolve(projectRoot, '..');

const args = {};
for (let i = 2; i < process.argv.length; i += 1) {
  const key = process.argv[i];
  if (!key.startsWith('--')) continue;
  args[key.slice(2)] = process.argv[i + 1];
  i += 1;
}

const scene = args.scene || 'attention-flow';
const fps = Number(args.fps || 30);
const width = Number(args.width || 1920);
const height = Number(args.height || 1080);
const failAt = Number(args['fail-at'] || 0);
const keepFrames = args['keep-frames'] === 'true';
const out = path.resolve(args.out || path.join(workspaceRoot, 'build', 'motion-canvas', `${scene}.mp4`));
const runId = `${scene}-${new Date().toISOString().replace(/[:.]/g, '-')}-${process.pid}`;
const runDir = path.join(workspaceRoot, 'build', 'motion-canvas', runId);
const frameDir = path.join(runDir, 'frames');
const metaPath = path.join(runDir, 'meta.json');
const logPath = path.join(runDir, 'render.log');
const sinkPort = Number(args['sink-port'] || 4174);
const vitePort = Number(args['vite-port'] || 4173);
const knownScenes = [
  'attention-flow',
  'gui-vs-cli-paths',
  'terminal-shell-layers',
  'argument-tokenization',
  'path-lookup-flow',
  'unix-pipeline-stream',
  'redirection-mechanics',
  'permission-shebang',
  'pipeline-case-demo',
];

if (!knownScenes.includes(scene)) {
  console.error(`unknown scene: ${scene}`);
  process.exit(2);
}

await mkdir(frameDir, {recursive: true});
await mkdir(path.dirname(out), {recursive: true});

const logLines = [];
const log = (line) => {
  const text = `[${new Date().toISOString()}] ${line}`;
  logLines.push(text);
  console.log(text);
};

let frameCount = 0;
let sinkState = {status: 'waiting', result: null, error: null};
let sinkResolve;
const sinkDone = new Promise((resolve) => { sinkResolve = resolve; });
const sink = createServer((req, res) => {
  const send = (code, body = '') => {
    res.writeHead(code, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Headers': 'Content-Type',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Content-Type': 'application/json',
    });
    res.end(body);
  };
  if (req.method === 'OPTIONS') return send(204);
  const url = new URL(req.url, `http://127.0.0.1:${sinkPort}`);
  const chunks = [];
  req.on('data', (chunk) => chunks.push(chunk));
  req.on('end', async () => {
    try {
      if (url.pathname === '/start') {
        const payload = JSON.parse(Buffer.concat(chunks).toString('utf8'));
        sinkState = {...sinkState, status: 'rendering', ...payload};
        log(`sink start ${JSON.stringify(payload)}`);
        return send(200, '{"ok":true}');
      }
      if (url.pathname === '/frame') {
        const index = Number(url.searchParams.get('frame'));
        if (!Number.isInteger(index) || index < 0) return send(400, '{"ok":false}');
        const target = path.join(frameDir, `frame-${String(index).padStart(6, '0')}.png`);
        await writeFile(target, Buffer.concat(chunks));
        frameCount += 1;
        return send(200, '{"ok":true}');
      }
      if (url.pathname === '/stop') {
        sinkState = {...sinkState, status: 'done', result: url.searchParams.get('result')};
        log(`sink stop ${JSON.stringify(sinkState)}`);
        sinkResolve(sinkState);
        return send(200, '{"ok":true}');
      }
      if (url.pathname === '/health') return send(200, '{"ok":true}');
      return send(404, '{"ok":false}');
    } catch (error) {
      sinkState = {...sinkState, status: 'error', error: String(error.stack || error)};
      log(`sink error ${sinkState.error}`);
      sinkResolve(sinkState);
      return send(500, '{"ok":false}');
    }
  });
});
await new Promise((resolve) => sink.listen(sinkPort, '127.0.0.1', resolve));
log(`frame sink on ${sinkPort}`);

const viteBin = path.join(projectRoot, 'node_modules', 'vite', 'bin', 'vite.js');
const vite = spawn(process.execPath, [viteBin, '--port', String(vitePort), '--strictPort'], {
  cwd: projectRoot,
  env: {...process.env, MOTION_CANVAS_HEADLESS: '1'},
  stdio: ['ignore', 'pipe', 'pipe'],
  shell: false,
});
vite.stdout.on('data', (data) => log(`vite: ${data.toString().trim()}`));
vite.stderr.on('data', (data) => log(`vite: ${data.toString().trim()}`));
vite.on('exit', (code) => log(`vite exit ${code}`));

const waitFor = async (url, timeoutMs = 60000) => {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // retry
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`timeout waiting for ${url}`);
};
await waitFor(`http://localhost:${vitePort}/headless.html`);

const playwrightEntry = path.join(workspaceRoot, 'RemotionStudio', 'node_modules', 'playwright', 'index.mjs');
const {chromium} = await import(pathToFileURL(playwrightEntry).href);
const browser = await chromium.launch({channel: 'chrome', headless: true});
let pageResult = null;
const pageErrors = [];
try {
  const page = await browser.newPage({viewport: {width: 640, height: 360}});
  page.on('console', (message) => {
    if (message.type() === 'error') pageErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(String(error)));
  const query = new URLSearchParams({
    scene,
    sink: `http://127.0.0.1:${sinkPort}`,
    fps: String(fps),
    width: String(width),
    height: String(height),
    failAt: String(failAt),
  });
  await page.goto(`http://localhost:${vitePort}/headless.html?${query}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForFunction(() => window.__RENDER_DONE__ === true, null, {
    timeout: 20 * 60 * 1000,
  });
  pageResult = await page.evaluate(() => ({
    result: window.__RENDER_RESULT__,
    errors: window.__RENDER_ERRORS__ || [],
  }));
  await page.waitForTimeout(500);
} finally {
  await browser.close();
  await new Promise((resolve) => sink.close(resolve));
  vite.kill();
}

const sinkFinal = await Promise.race([
  sinkDone,
  new Promise((resolve) => setTimeout(() => resolve(sinkState), 5000)),
]);
const frameFiles = await readdir(frameDir);
const meta = {
  schema_version: 1,
  kind: 'motion_canvas_headless_render',
  run_id: runId,
  scene,
  fps,
  width,
  height,
  requested_fail_at: failAt || null,
  frame_count: frameCount,
  frame_files: frameFiles.length,
  page_result: pageResult,
  page_errors: pageErrors,
  sink: sinkFinal,
  status: 'failed',
};
let exitCode = 1;

const ffprobe = (file) => new Promise((resolve) => {
  const probe = spawn('ffprobe', [
    '-v', 'error',
    '-select_streams', 'v:0',
    '-count_frames',
    '-show_entries', 'stream=width,height,r_frame_rate,nb_read_frames,duration',
    '-of', 'json',
    file,
  ], {stdio: ['ignore', 'pipe', 'pipe']});
  let stdout = '';
  probe.stdout.on('data', (data) => { stdout += data.toString(); });
  probe.on('close', (code) => {
    try {
      resolve({code, data: JSON.parse(stdout)});
    } catch {
      resolve({code, data: null, raw: stdout});
    }
  });
});

const expectedFrames = frameCount;
const contiguous = frameFiles.length === expectedFrames
  && Array.from({length: expectedFrames}, (_, i) => `frame-${String(i).padStart(6, '0')}.png`)
    .every((name) => frameFiles.includes(name));

if (
  sinkFinal.status === 'done'
  && sinkFinal.result === '0'
  && pageResult?.result === 'success'
  && frameCount > 0
  && contiguous
  && failAt === 0
) {
  const ffmpeg = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-framerate', String(fps),
    '-start_number', '0',
    '-i', path.join(frameDir, 'frame-%06d.png'),
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-crf', '18',
    '-movflags', '+faststart',
    out,
  ], {stdio: ['ignore', 'pipe', 'pipe']});
  let ffmpegError = '';
  ffmpeg.stderr.on('data', (data) => { ffmpegError += data.toString(); });
  const ffmpegCode = await new Promise((resolve) => ffmpeg.on('close', resolve));
  meta.ffmpeg = {code: ffmpegCode, stderr: ffmpegError.trim()};
  if (ffmpegCode === 0) {
    const probe = await ffprobe(out);
    meta.ffprobe = probe.data;
    const stream = probe.data?.streams?.[0] || {};
    const ok = stream.width === width
      && stream.height === height
      && Number(stream.nb_read_frames) === expectedFrames;
    meta.output = out;
    meta.sha256 = createHash('sha256').update(await readFile(out)).digest('hex');
    meta.status = ok ? 'pass' : 'failed';
    exitCode = ok ? 0 : 1;
  }
} else if (failAt > 0 && pageResult?.result === 'error') {
  meta.status = 'failed_as_injected';
  meta.error = `injected failure at frame ${failAt}`;
  exitCode = 0;
} else {
  meta.error = pageErrors.at(-1) || sinkFinal.error || 'render did not complete';
}

await writeFile(logPath, logLines.join('\n') + '\n', 'utf8');
await writeFile(metaPath, JSON.stringify(meta, null, 2) + '\n', 'utf8');
if (!keepFrames) await rm(frameDir, {recursive: true, force: true});
log(`result ${meta.status}; frames=${frameCount}; meta=${metaPath}`);
process.exitCode = exitCode;
