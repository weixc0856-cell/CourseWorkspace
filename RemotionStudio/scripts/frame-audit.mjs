// Audit rendered frames through the DOM, not through pixels.
//
// The audit bundles src/audit/index.tsx, a standalone Remotion Player page that
// accepts ?frame=N, then loads it at 1920x1080 and reads the box model.
//   node scripts/frame-audit.mjs [frame ...] [--no-bundle] [--selftest]
//
// Rules: text inside the 5% title-safe area, no clipped text, WCAG contrast
// (4.5 normal / 3.0 large, docs/配色规范.md), and no subtitle box covering an
// element marked data-evidence. Failures carry frame, selector and a PNG in
// <content_root>/build/frame-audit/frames/.

import { chromium } from 'playwright';
import { existsSync, mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { createServer } from 'node:http';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { contentRoot, workspace } from './content-root.mjs';

const COMPOSITION = { width: 1920, height: 1080 };
const DEFAULT_FRAMES = [15, 270, 555, 990, 1455, 2040, 2655, 3165, 3705, 4140];

const auditInPage = () => {
  const SAFE = 96;
  const scale = window.innerWidth / 1920;
  // The bundle page also carries studio chrome; audit only the composition.
  const player = document.querySelector('.__remotion-player');
  const canvases = [...document.querySelectorAll('div')].filter((element) => {
    const rect = element.getBoundingClientRect();
    return (
      Math.round(rect.width) === 1920 &&
      Math.round(rect.height) >= 1080 &&
      (element.innerText || '').trim().length > 0
    );
  });
  canvases.sort((a, b) => a.getBoundingClientRect().height - b.getBoundingClientRect().height);
  const scope = player || canvases[0] || document.body;
  const toComposition = (rect) => ({
    x: rect.left / scale,
    y: rect.top / scale,
    w: rect.width / scale,
    h: rect.height / scale,
  });

  const parseColor = (value) => {
    const match = /rgba?\(([^)]+)\)/.exec(value || '');
    if (!match) return null;
    const parts = match[1].split(',').map((item) => parseFloat(item));
    return { r: parts[0], g: parts[1], b: parts[2], a: parts.length > 3 ? parts[3] : 1 };
  };
  const channel = (value) => {
    const v = value / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  const luminance = (color) =>
    0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
  const ratio = (a, b) => {
    const la = luminance(a);
    const lb = luminance(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  };
  const blend = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a),
    g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a),
    a: 1,
  });

  const backgroundOf = (element) => {
    let current = element;
    let top = null;
    while (current && current !== document.documentElement) {
      const style = getComputedStyle(current);
      if (style.backgroundImage && style.backgroundImage !== 'none') {
        return null;
      }
      const color = parseColor(style.backgroundColor);
      if (color && color.a > 0) {
        top = top ? blend(top, color) : color;
        if (color.a === 1) return top;
      }
      current = current.parentElement;
    }
    const body = parseColor(getComputedStyle(document.body).backgroundColor);
    if (body && body.a > 0) return top ? blend(top, body) : body;
    return null;
  };

  const selectorOf = (element) => {
    if (element.id) return '#' + element.id;
    const parts = [];
    let current = element;
    while (current && current !== document.body && parts.length < 4) {
      const name = current.tagName.toLowerCase();
      const index = current.parentElement
        ? Array.from(current.parentElement.children).indexOf(current) + 1
        : 1;
      parts.unshift(name + ':nth-child(' + index + ')');
      current = current.parentElement;
    }
    return parts.join(' > ');
  };

  const issues = [];
  const notes = [];
  const textElements = [];
  const textBoxes = [];
  let skippedSymbolic = 0;
  for (const element of scope.querySelectorAll('*')) {
    if (element.closest('[data-audit-ignore]')) continue;
    const direct = Array.from(element.childNodes)
      .filter((node) => node.nodeType === Node.TEXT_NODE)
      .map((node) => node.textContent.trim())
      .join(' ')
      .trim();
    if (!direct) continue;
    const style = getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
    const rect = element.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) continue;
    // Icons and decorative glyphs are not text for layout or contrast purposes.
    if (!/[A-Za-z0-9À-ɏ]/.test(direct)) {
      skippedSymbolic += 1;
      continue;
    }
    const composed = toComposition(rect);
    if (
      composed.x < SAFE ||
      composed.y < SAFE ||
      composed.x + composed.w > 1920 - SAFE ||
      composed.y + composed.h > 1080 - SAFE
    ) {
      const overflow = Math.max(
        SAFE - composed.x,
        SAFE - composed.y,
        composed.x + composed.w - (1920 - SAFE),
        composed.y + composed.h - (1080 - SAFE),
      );
      issues.push({
        rule: 'safe_area',
        selector: selectorOf(element),
        text: direct.slice(0, 80),
        rect: composed,
        overflow_px: Math.round(overflow),
      });
    }
    const clips = [style.overflowX, style.overflowY].some((value) =>
      ['hidden', 'auto', 'scroll', 'clip'].includes(value),
    );
    if (
      clips &&
      (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1)
    ) {
      issues.push({
        rule: 'truncation',
        selector: selectorOf(element),
        text: direct.slice(0, 80),
        scroll: [element.scrollWidth, element.scrollHeight],
        client: [element.clientWidth, element.clientHeight],
      });
    }
    const fontSize = parseFloat(style.fontSize) || 16;
    const weight = parseInt(style.fontWeight, 10) || 400;
    const large = fontSize >= 24 || (fontSize >= 18.66 && weight >= 700);
    const foreground = parseColor(style.color);
    const background = backgroundOf(element);
    const hasLetters = true;
    if (foreground && background && hasLetters) {
      const value = ratio(foreground, background);
      const minimum = large ? 3.0 : 4.5;
      if (value < minimum) {
        issues.push({
          rule: 'contrast',
          selector: selectorOf(element),
          text: direct.slice(0, 80),
          ratio: Math.round(value * 100) / 100,
          minimum,
        });
      }
    } else {
      notes.push({ selector: selectorOf(element), note: 'background is an image or gradient; contrast skipped' });
    }
    textElements.push(selectorOf(element));
    textBoxes.push({element, selector: selectorOf(element), text: direct.slice(0, 80), rect: composed});
  }

  const area = (rect) => rect.w * rect.h;
  const overlapArea = (a, b) => {
    const w = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x));
    const h = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y));
    return w * h;
  };
  for (let i = 0; i < textBoxes.length; i += 1) {
    for (let j = i + 1; j < textBoxes.length; j += 1) {
      const a = textBoxes[i];
      const b = textBoxes[j];
      if (a.element.contains(b.element) || b.element.contains(a.element)) continue;
      const shared = overlapArea(a.rect, b.rect) / Math.min(area(a.rect), area(b.rect));
      if (shared > 0.05) {
        issues.push({
          rule: 'text_overlap',
          selector: a.selector,
          other: b.selector,
          text: a.text,
          other_text: b.text,
          ratio: Math.round(shared * 100) / 100,
        });
      }
    }
  }
  const figures = [...scope.querySelectorAll('[data-evidence], [data-figure]')].map((element) => ({
    id: element.getAttribute('data-evidence') || element.getAttribute('data-figure'),
    element,
    rect: toComposition(element.getBoundingClientRect()),
  }));
  for (const figure of figures) {
    if (!figure.element.querySelector('[data-source]')) {
      issues.push({rule: 'figure_source_missing', figure: figure.id, selector: selectorOf(figure.element)});
    }
  }
  for (const box of textBoxes) {
    for (const figure of figures) {
      if (figure.element.contains(box.element)) continue;
      const shared = overlapArea(box.rect, figure.rect) / Math.min(area(box.rect), area(figure.rect));
      if (shared > 0.05) {
        issues.push({
          rule: 'text_covers_figure',
          selector: box.selector,
          figure: figure.id,
          text: box.text,
          ratio: Math.round(shared * 100) / 100,
        });
      }
    }
  }

  const evidence = [...scope.querySelectorAll('[data-evidence]')].map((element) => ({
    id: element.getAttribute('data-evidence'),
    rect: toComposition(element.getBoundingClientRect()),
  }));
  const subtitles = [...scope.querySelectorAll('[data-subtitle]')].map((element) => ({
    id: element.getAttribute('data-subtitle'),
    rect: toComposition(element.getBoundingClientRect()),
    visible: parseFloat(getComputedStyle(element).opacity) > 0.05,
  }));
  const intersects = (a, b) =>
    a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  for (const subtitle of subtitles) {
    if (!subtitle.visible) continue;
    for (const item of evidence) {
      if (intersects(subtitle.rect, item.rect)) {
        issues.push({
          rule: 'subtitle_covers_evidence',
          selector: 'subtitle:' + subtitle.id,
          evidence: item.id,
          rect: subtitle.rect,
        });
      }
    }
  }

  return { issues, notes, text_count: textElements.length, skipped_symbolic: skippedSymbolic };
};

function startServer(root) {
  const types = {
    '.html': 'text/html',
    '.js': 'text/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.png': 'image/png',
    '.glb': 'model/gltf-binary',
  };
  return new Promise((ready) => {
    const server = createServer((request, response) => {
      const clean = decodeURIComponent((request.url || '/').split('?')[0]);
      const file = resolve(root, '.' + clean);
      if (!file.startsWith(root)) {
        response.statusCode = 403;
        response.end();
        return;
      }
      try {
        const data = readFileSync(file);
        const suffix = file.slice(file.lastIndexOf('.'));
        response.setHeader('Content-Type', types[suffix] || 'application/octet-stream');
        response.end(data);
      } catch {
        response.statusCode = 404;
        response.end('not found');
      }
    });
    server.listen(0, '127.0.0.1', () => ready(server));
  });
}

function frameUrl(baseUrl, frame) {
  return baseUrl + '/index.html?frame=' + frame;
}

async function openFrame(page, baseUrl, frame) {
  await page.goto(frameUrl(baseUrl, frame), { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.remotion_renderReady === true, null, { timeout: 45000 });
  await page.waitForTimeout(250);
}

async function main() {
  const args = process.argv.slice(2);
  const selftestMode = args.includes('--selftest');
  const noBundle = args.includes('--no-bundle');
  const dumpIndex = args.indexOf('--dump');
  const dumpDir = dumpIndex >= 0 ? args[dumpIndex + 1] : null;
  const from = Number(args[args.indexOf('--from') + 1] ?? 0);
  const to = Number(args[args.indexOf('--to') + 1] ?? 4590);
  const step = Number(args[args.indexOf('--step') + 1] ?? 15);
  const frames = args.map(Number).filter((value) => Number.isFinite(value) && value >= 0);
  const root = contentRoot();
  const outDir = resolve(root, 'build', 'frame-audit');
  const bundleDir = resolve(root, 'build', 'audit-bundle');
  const bundleIndex = resolve(bundleDir, 'index.html');
  mkdirSync(resolve(outDir, 'frames'), { recursive: true });

  if (!noBundle || !existsSync(bundleIndex)) {
    const studio = resolve(workspace, 'RemotionStudio');
    const result = spawnSync(
      process.execPath,
      [resolve(studio, 'node_modules', '@remotion', 'cli', 'remotion-cli.js'), 'bundle', 'src/audit/index.tsx', '--out-dir', bundleDir],
      { cwd: studio, stdio: 'inherit' },
    );
    if (result.status !== 0) {
      console.error('bundle failed');
      process.exit(1);
    }
  }

  const server = await startServer(bundleDir);
  const baseUrl = 'http://127.0.0.1:' + server.address().port;
  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
  });
  try {
    const page = await browser.newPage({ viewport: { width: COMPOSITION.width, height: COMPOSITION.height } });

    if (dumpDir) {
      mkdirSync(dumpDir, { recursive: true });
      let written = 0;
      for (let frame = from; frame <= to; frame += step) {
        await openFrame(page, baseUrl, frame);
        const target = resolve(dumpDir, `frame-${String(frame).padStart(5, '0')}.png`);
        await page.screenshot({ path: target });
        written += 1;
        if (written % 20 === 0) console.log(`  dumped ${written} frames`);
      }
      console.log(`dumped ${written} frames -> ${dumpDir}`);
      return;
    }

    if (selftestMode) {
      await openFrame(page, baseUrl, 0);
      const setup = await page.evaluate(() => {
        const player = document.querySelector('.__remotion-player');
        if (!player) return { injected: false, reason: 'player not found' };
        const host = document.createElement('div');
        host.setAttribute('data-audit-selftest', '');
        Object.assign(host.style, { position: 'absolute', left: '0px', top: '0px', width: '1920px', height: '1080px' });
        const evidence = document.createElement('div');
        evidence.setAttribute('data-evidence', 'selftest-evidence');
        Object.assign(evidence.style, { position: 'absolute', left: '400px', top: '300px', width: '600px', height: '400px' });
        const subtitle = document.createElement('div');
        subtitle.setAttribute('data-subtitle', 'selftest-subtitle');
        subtitle.textContent = 'SELFTEST';
        Object.assign(subtitle.style, {
          position: 'absolute',
          left: '500px',
          top: '420px',
          width: '300px',
          height: '50px',
          color: 'white',
          background: 'black',
        });
        host.append(evidence, subtitle);
        player.appendChild(host);
        return {
          injected: true,
          evidence_found: host.querySelectorAll('[data-evidence]').length,
          subtitle_found: host.querySelectorAll('[data-subtitle]').length,
        };
      });
      if (!setup.injected) {
        console.log('evidence_found: 0  injected: false  reason: ' + setup.reason);
        console.log('selftest: FAIL');
        process.exitCode = 1;
        return;
      }
      const overlapping = await page.evaluate(auditInPage);
      const caught = overlapping.issues.some(
        (item) => item.rule === 'subtitle_covers_evidence' && item.selector === 'subtitle:selftest-subtitle',
      );
      await page.evaluate(() => {
        const subtitle = document.querySelector('[data-subtitle="selftest-subtitle"]');
        if (subtitle) Object.assign(subtitle.style, { left: '0px', top: '0px' });
      });
      const separated = await page.evaluate(auditInPage);
      const falsePositive = separated.issues.some(
        (item) => item.rule === 'subtitle_covers_evidence' && item.selector === 'subtitle:selftest-subtitle',
      );
      const sourceSetup = await page.evaluate(() => {
        const player = document.querySelector('.__remotion-player');
        if (!player) return { injected: false };
        const figure = document.createElement('div');
        figure.setAttribute('data-figure', 'selftest-figure');
        Object.assign(figure.style, {
          position: 'absolute',
          left: '1200px',
          top: '700px',
          width: '300px',
          height: '200px',
          background: 'black',
        });
        player.appendChild(figure);
        return { injected: true };
      });
      const sourceMissing = await page.evaluate(auditInPage);
      const sourceCaught = sourceMissing.issues.some(
        (item) => item.rule === 'figure_source_missing' && item.figure === 'selftest-figure',
      );
      await page.evaluate(() => {
        const figure = document.querySelector('[data-figure="selftest-figure"]');
        if (!figure) return;
        const line = document.createElement('div');
        line.setAttribute('data-source', 'selftest');
        line.textContent = 'SELFTEST SOURCE';
        Object.assign(line.style, {
          position: 'absolute',
          left: '10px',
          bottom: '10px',
          color: 'white',
          background: 'black',
        });
        figure.appendChild(line);
      });
      const sourceFixed = await page.evaluate(auditInPage);
      const sourceFixedFalsePositive = sourceFixed.issues.some(
        (item) => item.rule === 'figure_source_missing' && item.figure === 'selftest-figure',
      );

      await page.evaluate(() => {
        const player = document.querySelector('.__remotion-player');
        if (!player) return;
        const host = document.createElement('div');
        Object.assign(host.style, {position: 'absolute', left: '0px', top: '0px', width: '1920px', height: '1080px'});
        const make = (left, top, value) => {
          const box = document.createElement('div');
          box.textContent = value;
          box.setAttribute('data-audit-selftest', '');
          Object.assign(box.style, {
            position: 'absolute',
            left: left + 'px',
            top: top + 'px',
            width: '300px',
            height: '60px',
            color: 'white',
            background: 'black',
          });
          return box;
        };
        host.append(make(1400, 1000, 'OVERLAP A'), make(1420, 1020, 'OVERLAP B'));
        player.appendChild(host);
      });
      const overlapAudit = await page.evaluate(auditInPage);
      const overlapCaught = overlapAudit.issues.some((item) => item.rule === 'text_overlap');
      await page.evaluate(() => {
        const target = [...document.querySelectorAll('[data-audit-selftest]')].find(
          (element) => element.textContent === 'OVERLAP B',
        );
        if (target) { target.style.left = '900px'; target.style.top = '1000px'; }
      });
      const overlapSeparated = await page.evaluate(auditInPage);
      const overlapFalsePositive = overlapSeparated.issues.some((item) => item.rule === 'text_overlap');
      console.log(
        'evidence_found: ' + setup.evidence_found +
          '  subtitles: ' + setup.subtitle_found +
          '  injected: true  overlapping_caught: ' + caught +
          '  separated_caught: ' + falsePositive +
          '  text_overlap_caught: ' + overlapCaught +
          '  text_overlap_separated: ' + overlapFalsePositive +
          '  source_missing_caught: ' + sourceCaught +
          '  source_fixed: ' + sourceFixedFalsePositive,
      );
      const ok =
        caught &&
        !falsePositive &&
        overlapCaught &&
        !overlapFalsePositive &&
        sourceCaught &&
        !sourceFixedFalsePositive;
      console.log('selftest: ' + (ok ? 'PASS' : 'FAIL'));
      process.exitCode = ok ? 0 : 1;
      return;
    }

    const list = frames.length ? frames : DEFAULT_FRAMES;
    const results = [];
    for (const frame of list) {
      await openFrame(page, baseUrl, frame);
      const result = await page.evaluate(auditInPage);
      const entry = {
        frame,
        issues: result.issues || [],
        notes: (result.notes || []).length,
        skipped_symbolic: result.skipped_symbolic || 0,
        error: result.error || null,
      };
      results.push(entry);
      console.log(
        `  frame ${frame}: ${entry.issues.length} issue(s), ${entry.skipped_symbolic} symbolic skipped` +
          (entry.error ? ' ERROR ' + entry.error : ''),
      );
      if (entry.issues.length) {
        const shot = resolve(outDir, 'frames', `frame-${frame}.png`);
        await page.screenshot({ path: shot });
        for (const issue of entry.issues) issue.evidence_png = shot;
      }
    }
    const skipped = results.reduce((total, entry) => total + entry.skipped_symbolic, 0);
    const report = { schema_version: 1, composition: COMPOSITION, frames: list, skipped_symbolic: skipped, results };
    writeFileSync(resolve(outDir, 'report.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
    const exceptions = results.flatMap((entry) =>
      entry.issues.map((issue) => ({ frame: entry.frame, ...issue })),
    );
    writeFileSync(
      resolve(outDir, 'exceptions.json'),
      JSON.stringify({ schema_version: 1, exceptions }, null, 2) + '\n',
      'utf8',
    );
    console.log(`report: ${resolve(outDir, 'report.json')}`);
    console.log(`exceptions: ${exceptions.length}  symbolic skipped: ${skipped}`);
    process.exitCode = exceptions.length ? 1 : 0;
  } finally {
    await browser.close();
    server.close();
  }
}

await main();
