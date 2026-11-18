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
const width = Number(args.width ?? 1920);
const height = Number(args.height ?? 1080);
if (!Number.isInteger(width) || !Number.isInteger(height) || width < 320 || height < 180) {
  console.error('ERROR: --width/--height must be integers >= 320x180');
  process.exit(2);
}

const pageLabel = (horizontal, vertical) =>
  String(horizontal + 1).padStart(3, '0') +
  (vertical > 0 ? String.fromCharCode(96 + vertical) : '');

const inspectSlideLayout = async (page) =>
  page.evaluate(() => {
    const section = document.querySelector('.reveal .slides section.present');
    if (!section) {
      return {ok: false, issues: ['no present slide section']};
    }

    const sectionRect = section.getBoundingClientRect();
    const selector = 'h1,h2,h3,h4,p,li,figcaption,img,table,pre,blockquote';
    const candidates = Array.from(section.querySelectorAll(selector)).filter((element) => {
      if (element.closest('[data-layout-ignore]')) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        Number(style.opacity) > 0 &&
        rect.width > 1 &&
        rect.height > 1
      );
    });

    // Keep leaf content blocks only.  Parent wrappers contain child text and
    // would otherwise report artificial overlaps with their own descendants.
    const leaves = candidates.filter(
      (element) =>
        !candidates.some(
          (other) => other !== element && element.contains(other),
        ),
    );

    const issues = [];
    const tolerance = 2;
    if (
      section.scrollHeight > section.clientHeight + tolerance ||
      section.scrollWidth > section.clientWidth + tolerance
    ) {
      issues.push(
        `section overflow ${section.scrollWidth}x${section.scrollHeight} ` +
          `> ${section.clientWidth}x${section.clientHeight}`,
      );
    }

    const boxes = leaves.map((element) => ({
      element,
      rect: element.getBoundingClientRect(),
      label:
        element.tagName.toLowerCase() +
        (element.className ? `.${String(element.className).trim().replace(/\s+/g, '.')}` : ''),
    }));

    for (const box of boxes) {
      const {left, top, right, bottom} = box.rect;
      if (
        left < sectionRect.left - tolerance ||
        top < sectionRect.top - tolerance ||
        right > sectionRect.right + tolerance ||
        bottom > sectionRect.bottom + tolerance
      ) {
        issues.push(`${box.label} extends outside the slide`);
      }
    }

    const overlapArea = (a, b) => {
      const width = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left));
      const height = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
      return width * height;
    };

    for (let i = 0; i < boxes.length; i += 1) {
      for (let j = i + 1; j < boxes.length; j += 1) {
        const area = overlapArea(boxes[i].rect, boxes[j].rect);
        if (area > 4) {
          issues.push(
            `${boxes[i].label} overlaps ${boxes[j].label} (${Math.round(area)} px^2)`,
          );
        }
      }
    }

    return {
      ok: issues.length === 0,
      issues: issues.slice(0, 20),
    };
  });

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
    viewport: {width, height},
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
    const layout = await inspectSlideLayout(page);
    if (!layout.ok) {
      throw new Error(
        `slide ${pageNumber} layout audit failed:\n- ${layout.issues.join('\n- ')}`,
      );
    }
    const file = `slide-${pageNumber}.png`;
    const target = path.join(outDir, file);
    await page.screenshot({path: target, fullPage: false});
    const info = await stat(target);
    if (info.size <= 0) throw new Error(`empty screenshot: ${target}`);
    pages.push({
      index,
      page: pageNumber,
      file,
      width,
      height,
      bytes: info.size,
      layout_audit: 'pass',
    });
    console.log(`AUDIT ${pageNumber} PASS`);
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
        viewport: [width, height],
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
