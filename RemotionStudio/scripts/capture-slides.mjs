import {mkdir, stat, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

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
const lesson = args.lesson;
if (!lesson) {
  console.error('ERROR: --lesson <slug> is required');
  process.exit(2);
}
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(lesson)) {
  console.error(`ERROR: invalid lesson slug: ${lesson}`);
  process.exit(2);
}

const baseUrl = args['base-url'] ?? 'http://localhost:8081';
const outDir = path.resolve(args.out ?? path.join(workspaceRoot, 'build', lesson, 'slides'));
const maxPages = args.max ? Number(args.max) : null;
const preferredChannel = args.channel ?? 'chrome';

const pageLabel = (horizontal, vertical) =>
  String(horizontal + 1).padStart(3, '0') +
  (vertical > 0 ? String.fromCharCode(96 + vertical) : '');

const launch = async () => {
  const channels = [preferredChannel, preferredChannel === 'chrome' ? 'msedge' : 'chrome'];
  let lastError;
  for (const channel of channels) {
    try {
      const browser = await chromium.launch({channel, headless: true});
      console.log(`BROWSER ${channel}`);
      return browser;
    } catch (error) {
      lastError = error;
      console.error(`WARN: cannot launch ${channel}: ${error.message.split('\n')[0]}`);
    }
  }
  throw lastError;
};

await mkdir(outDir, {recursive: true});

const browser = await launch();
try {
  const page = await browser.newPage({
    viewport: {width: 1920, height: 1080},
    deviceScaleFactor: 1,
  });

  const url = `${baseUrl}/CourseSlides/template/?lesson=${lesson}`;
  console.log(`CAPTURE ${url}`);
  const response = await page.goto(url, {waitUntil: 'networkidle', timeout: 60000});
  if (!response || !response.ok()) {
    throw new Error(`page load failed: ${response ? response.status() : 'no response'}`);
  }

  await page.waitForFunction(
    () => Boolean(window.Reveal && window.Reveal.isReady && window.Reveal.isReady()),
    null,
    {timeout: 30000},
  );

  await page.addStyleTag({
    content:
      '.reveal .controls, .reveal .progress, .reveal .slide-number { display: none !important; }',
  });

  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(
      Array.from(document.images).map((image) =>
        image.complete
          ? Promise.resolve()
          : new Promise((resolve) => {
              image.addEventListener('load', resolve, {once: true});
              image.addEventListener('error', resolve, {once: true});
            }),
      ),
    );
  });

  const total = await page.evaluate(() => window.Reveal.getTotalSlides());
  if (!Number.isInteger(total) || total < 1) {
    throw new Error(`invalid slide count: ${total}`);
  }
  console.log(`TOTAL ${total}`);

  await page.evaluate(() => window.Reveal.slide(0, 0));

  const pages = [];
  let index = 0;
  while (true) {
    await page.waitForTimeout(900);
    const indices = await page.evaluate(() => window.Reveal.getIndices());
    const pageNumber = pageLabel(indices.h, indices.v);
    const file = `slide-${pageNumber}.png`;
    const target = path.join(outDir, file);
    await page.screenshot({path: target, fullPage: false});
    const info = await stat(target);
    if (info.size <= 0) throw new Error(`empty screenshot: ${target}`);
    pages.push({index, page: pageNumber, file, width: 1920, height: 1080, bytes: info.size});
    console.log(`WROTE ${file} (${info.size} bytes)`);

    index += 1;
    if (maxPages && index >= maxPages) break;
    const isLast = await page.evaluate(() => window.Reveal.isLastSlide());
    if (isLast) break;
    await page.evaluate(() => window.Reveal.next());
  }

  if (!maxPages && pages.length !== total) {
    throw new Error(`captured ${pages.length} pages, expected ${total}`);
  }

  await writeFile(
    path.join(outDir, 'capture-manifest.json'),
    JSON.stringify(
      {
        lesson,
        generated_at: new Date().toISOString(),
        source: 'auto',
        viewport: [1920, 1080],
        total_slides: total,
        captured: pages.length,
        pages,
      },
      null,
      2,
    ) + '\n',
    'utf8',
  );
  console.log(`CAPTURE_OK ${pages.length}/${total}`);
} catch (error) {
  console.error(`ERROR: ${error.stack ?? error.message}`);
  process.exitCode = 1;
} finally {
  await browser.close();
}
