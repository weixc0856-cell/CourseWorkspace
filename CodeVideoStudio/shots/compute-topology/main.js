const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920, H = 1080, DURATION = 26;

const C = {
  bg: '#FBFAF7', ink: '#252A31', muted: '#6B7280', line: '#E3E0D7',
  surface: '#F3F1EA', accent: '#E8733B', blue: '#4A82B8', teal: '#42A69A',
  purple: '#7A6FB0', red: '#C75B55', white: '#FFFFFF',
};

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => { const v = clamp01(x); return v * v * (3 - 2 * v); };
const prog = (t, a, b) => ease((t - a) / (b - a));
const font = (w, s) => `${w} ${s}px "Segoe UI", Aptos, Helvetica, Arial, sans-serif`;
const mono = (w, s) => `${w} ${s}px "Cascadia Mono", Consolas, monospace`;

function text(str, x, y, size, color, weight = '400', align = 'left', alpha = 1, family = 'sans', tracking = 0) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  ctx.font = family === 'mono' ? mono(weight, size) : font(weight, size);
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  if (tracking) ctx.letterSpacing = tracking + 'px';
  ctx.fillText(str, x, y);
  ctx.letterSpacing = '0px';
  ctx.restore();
}

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function box(x, y, w, h, alpha, stroke, fill, dashed, width) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  if (fill) { ctx.fillStyle = fill; roundRect(x, y, w, h, 12); ctx.fill(); }
  ctx.strokeStyle = stroke; ctx.lineWidth = width || 2;
  if (dashed) ctx.setLineDash([12, 9]);
  roundRect(x, y, w, h, 12); ctx.stroke();
  ctx.restore();
}

function arrowHead(x, y, angle, color, alpha, size = 16) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  ctx.translate(x, y); ctx.rotate(angle);
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(-size, size * 0.55); ctx.lineTo(-size, -size * 0.55); ctx.closePath(); ctx.fill();
  ctx.restore();
}

const DC = { x: 110, y: 300, w: 600, h: 420 };
const CLOUD = { x: 940, y: 420, w: 320, h: 180 };
const CLIENTS = [
  { x: 1420, y: 320, w: 380, h: 110, name: 'Client A', where: 'region one' },
  { x: 1420, y: 470, w: 380, h: 110, name: 'Client B', where: 'region two' },
  { x: 1420, y: 620, w: 380, h: 110, name: 'Client C', where: 'region three' },
];

function drawHeader(t) {
  const a = prog(t, 0, 1.2);
  text('PHYSICAL BOUNDARY', 120, 104, 24, C.accent, '600', 'left', a, 'sans', 4);
  text('The card stays. The work travels.', 120, 168, 60, C.ink, '600', 'left', a);
  text('Illustrative scenario: one data hall, many remote users', 122, 222, 28, C.muted, '400', 'left', prog(t, 0.8, 2.0));
}

function drawDatacenter(t) {
  const a = prog(t, 2.2, 3.6);
  if (a <= 0) return;
  box(DC.x, DC.y, DC.w, DC.h, a, C.ink, C.surface, false, 2.5);
  text('DATA HALL  SINGAPORE', DC.x + 34, DC.y + 44, 21, C.muted, '600', 'left', a, 'sans', 2);
  text('10,000 cards, none in transit', DC.x + 34, DC.y + 82, 30, C.ink, '600', 'left', a);

  let n = 0;
  for (let r = 0; r < 5; r++) {
    for (let c = 0; c < 10; c++) {
      const local = prog(t, 3.0 + n * 0.018, 3.4 + n * 0.018);
      if (local <= 0) { n++; continue; }
      ctx.save();
      ctx.globalAlpha *= local;
      ctx.fillStyle = C.blue;
      roundRect(DC.x + 40 + c * 54, DC.y + 130 + r * 44, 40, 28, 5); ctx.fill();
      ctx.restore();
      n++;
    }
  }
  text('schematic', DC.x + DC.w - 34, DC.y + DC.h - 30, 20, C.muted, '500', 'right', a);
}

function drawCloud(t) {
  const a = prog(t, 6.0, 7.4);
  if (a <= 0) return;
  box(CLOUD.x, CLOUD.y, CLOUD.w, CLOUD.h, a, C.purple, C.white, false, 2.5);
  text('CLOUD', CLOUD.x + CLOUD.w / 2, CLOUD.y + 54, 22, C.muted, '600', 'center', a, 'sans', 3);
  text('API gateway', CLOUD.x + CLOUD.w / 2, CLOUD.y + 96, 30, C.ink, '600', 'center', a);
  text('remote clusters', CLOUD.x + CLOUD.w / 2, CLOUD.y + 138, 22, C.muted, '400', 'center', a);
}

function drawClients(t) {
  CLIENTS.forEach((c, i) => {
    const a = prog(t, 8.8 + i * 0.5, 10.0 + i * 0.5);
    if (a <= 0) return;
    box(c.x, c.y, c.w, c.h, a, C.line, C.white, false, 1.5);
    text(c.name, c.x + 32, c.y + 40, 28, C.ink, '600', 'left', a);
    text(c.where, c.x + 32, c.y + 76, 22, C.muted, '400', 'left', a);
  });
}

function flow(x1, y1, x2, y2, t, start, color, alpha, reverse) {
  if (alpha <= 0) return;
  const ang = Math.atan2(y2 - y1, x2 - x1);
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.setLineDash([7, 7]);
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  ctx.restore();
  arrowHead(x2, y2, ang, color, alpha);

  // travelling packets
  const period = 2.4;
  for (let k = 0; k < 2; k++) {
    const local = (t - start - k * (period / 3)) / period;
    if (local < 0) continue;
    const p = reverse ? 1 - (local % 1) : (local % 1);
    const px = x1 + (x2 - x1) * p;
    const py = y1 + (y2 - y1) * p;
    ctx.save();
    ctx.globalAlpha *= alpha;
    ctx.fillStyle = color;
    ctx.beginPath(); ctx.arc(px, py, 6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }
}

function drawFlows(t) {
  const base = prog(t, 10.6, 12.0);
  CLIENTS.forEach((c, i) => {
    if (base <= 0) return;
    flow(c.x - 24, c.y + c.h / 2, CLOUD.x + CLOUD.w + 24, CLOUD.y + 60 + i * 30, t, 10.8 + i * 0.2, C.ink, base, false);
  });
  const b2 = prog(t, 12.0, 13.4);
  if (b2 > 0) {
    flow(CLOUD.x - 24, CLOUD.y + 70, DC.x + DC.w + 24, DC.y + 190, t, 12.2, C.accent, b2, false);
    flow(DC.x + DC.w + 24, DC.y + 250, CLOUD.x - 24, CLOUD.y + 110, t, 12.9, C.teal, b2 * 0.9, false);
    text('requests in', (DC.x + DC.w + CLOUD.x) / 2, 462, 19, C.accent, '600', 'center', b2, 'sans', 1);
    text('results out', (DC.x + DC.w + CLOUD.x) / 2, 578, 19, C.teal, '600', 'center', b2 * 0.9, 'sans', 1);
  }
}

function drawVerdict(t) {
  const a = prog(t, 17.6, 19.2);
  if (a <= 0) return;
  const w = 1680 * ease(prog(t, 17.8, 19.4));
  ctx.save();
  ctx.globalAlpha *= a;
  ctx.fillStyle = C.line;
  ctx.fillRect(120, 770, w, 2);
  ctx.restore();

  text('PHYSICAL LOCATION', 120, 816, 20, C.muted, '600', 'left', prog(t, 18.2, 19.4), 'sans', 3);
  text('One country.', 120, 860, 34, C.ink, '600', 'left', prog(t, 18.4, 19.6));

  text('WHO IS USING IT', 1090, 816, 20, C.muted, '600', 'left', prog(t, 19.0, 20.2), 'sans', 3);
  text('Anywhere.', 1090, 860, 34, C.accent, '600', 'left', prog(t, 19.2, 20.4));

  const g = prog(t, 19.6, 21.0);
  ctx.save();
  ctx.globalAlpha *= g;
  ctx.strokeStyle = C.red; ctx.lineWidth = 2.5; ctx.setLineDash([10, 8]);
  ctx.beginPath(); ctx.moveTo(1000, 786); ctx.lineTo(1000, 890); ctx.stroke();
  ctx.restore();
  ctx.save();
  ctx.globalAlpha *= g;
  ctx.fillStyle = C.bg;
  ctx.fillRect(962, 814, 76, 42);
  ctx.restore();
  text('gap', 1000, 835, 22, C.red, '600', 'center', g);
}

function draw(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);
  drawHeader(t);
  drawDatacenter(t);
  drawCloud(t);
  drawClients(t);
  drawFlows(t);
  drawVerdict(t);
}

window.DUR = DURATION;
window.seek = async (t) => { draw(Math.max(0, Math.min(DURATION, t))); };
draw(0);
document.fonts.ready.then(() => { window.READY = true; });
