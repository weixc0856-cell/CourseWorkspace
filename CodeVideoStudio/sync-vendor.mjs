// Copy the canonical three.js into every shot that needs it.
// The Python adapter does the same before capture; this script is for manual runs.
import fs from 'node:fs';
import path from 'node:path';

const root = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const source = path.join(root, 'vendor', 'three', 'three.module.js');
const shots = path.join(root, 'shots');
if (!fs.existsSync(source)) throw new Error(`missing canonical file: ${source}`);
let copied = 0;
for (const name of fs.readdirSync(shots)) {
  const dir = path.join(shots, name);
  if (!fs.statSync(dir).isDirectory()) continue;
  const page = path.join(dir, 'index.html');
  if (!fs.existsSync(page)) continue;
  if (!fs.readFileSync(page, 'utf8').includes('three.module.js')) continue;
  fs.copyFileSync(source, path.join(dir, 'three.module.js'));
  copied += 1;
}
console.log(`copied three.module.js into ${copied} shot(s)`);
