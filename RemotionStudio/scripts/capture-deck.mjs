import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { contentPath } from './content-root.mjs';

const dir = contentPath('build', 't1-01-sample');
const deck = pathToFileURL(dir + '/deck.html').href;
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(deck, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  await page.screenshot({ path: dir + '/deck-01.png' });
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(900);
  await page.screenshot({ path: dir + '/deck-02.png' });
  console.log('label:', await page.locator('#label').innerText());
  console.log('edit:', await page.locator('#edit').getAttribute('href'));
} finally { await browser.close(); }
