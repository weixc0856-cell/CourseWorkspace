import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '../RemotionStudio/node_modules/playwright/index.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const contentRoot = path.resolve('D:/CourseContent');
const lessonSlug = process.argv[2] || 't1-01-why-aerodynamics';
const buildDir = path.join(contentRoot, 'build', lessonSlug);
const shotsOutDir = path.join(buildDir, 'shots');
const htmlFile = path.join(buildDir, 'index.html');

if (!fs.existsSync(shotsOutDir)) {
  fs.mkdirSync(shotsOutDir, { recursive: true });
}

async function capture() {
  const fileUrl = 'file:///' + htmlFile.replace(/\\/g, '/');
  console.log(`[Playwright] Opening local file from Content Root: ${fileUrl}`);

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

  let count = 0;
  for (let i = 0; i < totalSlides; i++) {
    await page.evaluate((idx) => window.Reveal.slide(idx), i);
    await page.waitForTimeout(300);

    const slideNum = String(i + 1).padStart(2, '0');
    for (let step = 1; step <= 3; step++) {
      await page.evaluate((s) => window.setSlideStep(s), step);
      await page.waitForTimeout(200);

      const shotName = `shot-${slideNum}-step-${step}.png`;
      const outPath = path.join(shotsOutDir, shotName);
      await page.screenshot({ path: outPath });
      count++;
      console.log(`[Captured ${count}/33] ${shotName}`);
    }
  }

  await browser.close();
  console.log(`[Playwright] Done capturing all 33 shots to ${shotsOutDir}`);
}

capture().catch((err) => {
  console.error('[Error during capture]', err);
  process.exit(1);
});
