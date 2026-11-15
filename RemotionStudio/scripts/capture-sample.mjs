import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { contentPath } from './content-root.mjs';

const dir = contentPath('build', 't1-01-sample');
const pages = ['page01', 'page02', 'page03', 'page04', 'page05', 'page06'];
const base = pathToFileURL(dir).href;
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const name of pages) {
    await page.goto(base + '/' + name + '.html', { waitUntil: 'networkidle' });
    await page.evaluate(async () => { await document.fonts.ready; });
    await page.waitForTimeout(700);
    if (await page.locator('.katex').count()) { await page.waitForTimeout(300); }
    await page.screenshot({ path: dir + '/' + name + '.png' });
    console.log('WROTE', name);
  }
} finally { await browser.close(); }
