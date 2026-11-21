// Positive assertion: the bottom-left source citation never overlaps the
// centered low_center bilingual subtitle block, and never crowds the body.
// Renders example en/zh subtitles onto the given deck pages, measures real DOM
// rects, and fails (exit 1) on any intersection.  Owner hard requirement.
import {mkdir} from 'node:fs/promises';
import path from 'node:path';
import {chromium} from 'playwright';

const args = {};
for (let i = 2; i < process.argv.length; i += 2) args[process.argv[i].replace(/^--/, '')] = process.argv[i + 1];
const url = args.url;
const outDir = args.out;
const pages = (args.pages ?? '0,1').split(',').map(Number);
if (!url || !outDir) {
  console.error('usage: node verify-subtitle-overlap.mjs --url <deck url> --out <dir> [--pages 0,1]');
  process.exit(2);
}
await mkdir(outDir, {recursive: true});

const EN = 'The wake is where the drag lives.';
const ZH = '尾流才是阻力所在。';

const browser = await chromium.launch();
let failures = 0;
try {
  const page = await browser.newPage({viewport: {width: 1920, height: 1080}, deviceScaleFactor: 1});
  const response = await page.goto(url, {waitUntil: 'networkidle', timeout: 60000});
  if (!response || !response.ok()) throw new Error(`page load failed: ${response?.status}`);
  await page.waitForFunction(() => Boolean(window.Reveal?.isReady?.()), null, {timeout: 30000});
  await page.addStyleTag({content: '.reveal .controls, .reveal .progress, .reveal .slide-number { display: none !important; } .reveal .slides section { transition: none !important; }'});
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all(Array.from(document.images).map((im) => im.complete ? Promise.resolve() : new Promise((r) => {im.addEventListener('load', r, {once: true}); im.addEventListener('error', r, {once: true});})));
  });

  for (const index of pages) {
    await page.evaluate((i) => window.Reveal.slide(i, 0), index);
    await page.waitForTimeout(300);
    const rects = await page.evaluate(({en, zh}) => {
      const slide = window.Reveal.getCurrentSlide();
      const old = slide.querySelector('.subtitle-probe');
      if (old) old.remove();
      const probe = document.createElement('div');
      probe.className = 'subtitle-probe';
      // low_center safe zone: bottom 0-150px, centered column, en above zh.
      probe.style.cssText = 'position:absolute;left:50%;transform:translateX(-50%);bottom:0;max-width:760px;'
        + 'text-align:center;color:#fff;font-family:Inter,Helvetica,Arial,sans-serif;'
        + 'text-shadow:0 0 6px #000,0 2px 4px #000;z-index:60;pointer-events:none;';
      probe.innerHTML = `<div style="font-size:40px;line-height:1.25;">${en}</div>`
        + `<div style="font-size:34px;line-height:1.25;">${zh}</div>`;
      slide.appendChild(probe);
      const r = (el) => {const b = el.getBoundingClientRect(); return {left: b.left, top: b.top, right: b.right, bottom: b.bottom};};
      const source = slide.querySelector('.slide-footer .source');
      const visual = slide.querySelector('.main-visual');
      const sourceSingle = source
        ? (source.scrollWidth <= source.clientWidth + 1 && source.getClientRects().length === 1)
        : null;
      return {source: source ? r(source) : null, subtitle: r(probe), visual: visual ? r(visual) : null, sourceSingle};
    }, {en: EN, zh: ZH});
    await page.waitForTimeout(120);
    const shot = path.join(outDir, `subtitle-overlay-p${index + 1}.png`);
    await page.screenshot({path: shot});

    const s = rects.source, b = rects.subtitle, v = rects.visual;
    const overlap = s && !(s.right <= b.left || b.right <= s.left || s.bottom <= b.top || b.bottom <= s.top);
    const crowdsBody = v && s && s.top < v.bottom;
    const sourceTooHigh = s && s.top < 880;
    const visualTooLow = v && v.bottom > 831;
    const singleLine = rects.sourceSingle !== false;
    const ok = !overlap && !crowdsBody && !sourceTooHigh && !visualTooLow && singleLine;
    if (!ok) failures += 1;
    console.log(JSON.stringify({page: index + 1, source: s, subtitle: b, visualBottom: v?.bottom, overlap, crowdsBody, sourceTooHigh, visualTooLow, singleLine, ok, shot}));
  }
} finally {
  await browser.close();
}
process.exit(failures ? 1 : 0);