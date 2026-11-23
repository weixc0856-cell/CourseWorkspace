import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '../RemotionStudio/node_modules/playwright/index.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const contentRoot = path.resolve('D:/CourseContent');
const lessonSlug = 't1-01-why-aerodynamics';
const buildDir = path.join(contentRoot, 'build', lessonSlug);
const slidesOutDir = path.join(buildDir, 'slides');
const htmlFile = path.join(buildDir, 'index.html');

if (!fs.existsSync(slidesOutDir)) {
  fs.mkdirSync(slidesOutDir, { recursive: true });
}

async function capture() {
  const fileUrl = 'file:///' + htmlFile.replace(/\\/g, '/');
  console.log(`[Playwright] Opening local file: ${fileUrl}`);

  const browser = await chromium.launch({
    headless: true,
    args: ['--allow-file-access-from-files', '--disable-web-security']
  });
  
  const page = await browser.newPage({
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 1
  });

  await page.goto(fileUrl, { waitUntil: 'load' });
  await page.waitForFunction(() => window.Reveal && window.Reveal.isReady());
  const totalSlides = await page.evaluate(() => window.Reveal.getTotalSlides());
  console.log(`[Playwright] Total slides discovered: ${totalSlides}`);

  for (let i = 0; i < totalSlides; i++) {
    await page.evaluate((idx) => window.Reveal.slide(idx), i);
    await page.waitForTimeout(300);

    const slideNum = String(i + 1).padStart(3, '0');
    const outPath = path.join(slidesOutDir, `slide-${slideNum}.png`);
    await page.screenshot({ path: outPath });
    console.log(`[Captured] slide-${slideNum}.png (${i + 1}/${totalSlides})`);
  }

  await browser.close();
  console.log('[Playwright] Done capturing all 11 slides.');
}

capture().catch((err) => {
  console.error('[Error during capture]', err);
  process.exit(1);
});
