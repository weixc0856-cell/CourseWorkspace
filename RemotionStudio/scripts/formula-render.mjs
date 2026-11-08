// Render one FormulaSpec JSON to HTML/SVG + PNG.
// Usage:
//   node scripts/formula-render.mjs --spec <formula.json> --out <dir> [--engine katex|mathjax]
// KaTeX is the primary static renderer; MathJax is the SVG fallback for
// commands/constructs KaTeX cannot handle.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import katex from 'katex';
import {chromium} from 'playwright';
import {mathjax} from 'mathjax-full/js/mathjax.js';
import {TeX} from 'mathjax-full/js/input/tex.js';
import {SVG} from 'mathjax-full/js/output/svg.js';
import {liteAdaptor} from 'mathjax-full/js/adaptors/liteAdaptor.js';
import {RegisterHTMLHandler} from 'mathjax-full/js/handlers/html.js';
import {AllPackages} from 'mathjax-full/js/input/tex/AllPackages.js';

const require = createRequire(import.meta.url);
const katexRoot = path.dirname(require.resolve('katex/package.json'));

const argv = process.argv.slice(2);
const opt = (name, fallback = null) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : fallback;
};

const specPath = opt('spec');
const outDir = opt('out');
if (!specPath || !outDir) {
  console.error('usage: node scripts/formula-render.mjs --spec <formula.json> --out <dir> [--engine katex|mathjax]');
  process.exit(2);
}

const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
if (typeof spec.latex !== 'string' || !spec.latex.trim()) {
  console.error('FormulaSpec.latex is empty');
  process.exit(2);
}

const engine = String(opt('engine', spec.engine ?? 'katex')).toLowerCase();
if (!['katex', 'mathjax'].includes(engine)) {
  console.error(`unsupported formula engine: ${engine}`);
  process.exit(2);
}
const displayMode = spec.display !== 'inline';
const fontSize = Number(opt('font-size', spec.font_size ?? 48));
const color = opt('color', spec.color ?? '#14213D');
const outRoot = path.resolve(outDir);
fs.mkdirSync(outRoot, {recursive: true});

let htmlBody;
let svgPath = null;
let engineVersion = null;
if (engine === 'katex') {
  try {
    htmlBody = katex.renderToString(spec.latex, {
      displayMode,
      throwOnError: true,
      strict: 'error',
      output: 'html',
      trust: false,
    });
  } catch (error) {
    console.error(`KaTeX compile failed: ${error.message}`);
    process.exit(1);
  }
  engineVersion = katex.version;
} else {
  try {
    const adaptor = liteAdaptor();
    RegisterHTMLHandler(adaptor);
    const tex = new TeX({packages: AllPackages});
    const svg = new SVG({fontCache: 'local'});
    const document = mathjax.document('', {InputJax: tex, OutputJax: svg});
    const node = document.convert(spec.latex, {display: displayMode});
    htmlBody = adaptor.outerHTML(node);
    svgPath = path.join(outRoot, 'formula.svg');
    fs.writeFileSync(svgPath, htmlBody + '\n', 'utf8');
  } catch (error) {
    console.error(`MathJax compile failed: ${error.message}`);
    process.exit(1);
  }
  engineVersion = '3.2.2';
}

const htmlPath = path.join(outRoot, 'formula.html');
const pngPath = path.join(outRoot, 'formula.png');
const cssPath = path.join(katexRoot, 'dist', 'katex.min.css');
const doc = `<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="file:///${cssPath.replaceAll('\\', '/')}">
<style>
  html,body {margin:0;padding:0;background:transparent;}
  #formula {display:inline-block;padding:18px 22px;color:${color};font-size:${fontSize}px;}
  #formula svg {display:block;max-width:none;}
  .katex-display {margin:0;}
</style></head>
<body><div id="formula">${htmlBody}</div></body></html>`;
fs.writeFileSync(htmlPath, doc, 'utf8');

const browser = await chromium.launch({
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({viewport: {width: 2200, height: 1000}, deviceScaleFactor: 1});
await page.goto(`file:///${htmlPath.replaceAll('\\', '/')}`);
await page.waitForTimeout(400);
const box = await page.locator('#formula').boundingBox();
if (!box || box.width < 4 || box.height < 4) {
  await browser.close();
  console.error('rendered formula has an empty bounding box');
  process.exit(1);
}
await page.locator('#formula').screenshot({path: pngPath, omitBackground: true});
await browser.close();

const result = {
  formula_id: spec.formula_id ?? null,
  latex: spec.latex,
  display: displayMode ? 'block' : 'inline',
  engine,
  engine_version: engineVersion,
  html: htmlPath,
  svg: svgPath,
  png: pngPath,
  width: Math.round(box.width),
  height: Math.round(box.height),
  invisible_glyphs: /katex-error|merror/.test(htmlBody),
};
fs.writeFileSync(path.join(outRoot, 'formula.render.json'), JSON.stringify(result, null, 2) + '\n', 'utf8');
console.log(JSON.stringify(result));
if (result.invisible_glyphs) process.exit(1);
