const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920, H = 1080, DURATION = 24;

const C = {
  bg: '#FBFAF7', ink: '#252A31', body: '#2E3338', muted: '#6B7280',
  line: '#E3E0D7', surface: '#F3F1EA', accent: '#E8733B',
  blue: '#4A82B8', teal: '#42A69A', red: '#C75B55', navy: '#12324A', white: '#FFFFFF',
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

function panel(x, y, w, h, alpha, accent, dashed) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = C.white;
  roundRect(x, y, w, h, 10); ctx.fill();
  ctx.lineWidth = accent ? 2.5 : 1.5;
  ctx.strokeStyle = accent ? C.accent : C.line;
  if (dashed) ctx.setLineDash([12, 9]);
  roundRect(x, y, w, h, 10); ctx.stroke();
  ctx.restore();
}

function chip(label, x, y, alpha, color) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.font = font('500', 26);
  const w = ctx.measureText(label).width + 44;
  ctx.fillStyle = C.surface;
  roundRect(x, y, w, 56, 8); ctx.fill();
  ctx.strokeStyle = color; ctx.lineWidth = 1.5;
  roundRect(x, y, w, 56, 8); ctx.stroke();
  ctx.fillStyle = color;
  ctx.textAlign = 'left'; ctx.textBaseline = 'middle';
  ctx.fillText(label, x + 22, y + 29);
  ctx.restore();
  return w;
}

function line(x1, y1, x2, y2, color, alpha, width = 2, dash = null) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.strokeStyle = color; ctx.lineWidth = width; ctx.lineCap = 'round';
  if (dash) ctx.setLineDash(dash);
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  ctx.restore();
}

const CARD = { x: 130, y: 373, w: 300, h: 210 };
const PANEL = { x: 610, w: 1180, h: 172 };
const ROWS = [200, 392, 584];

function drawHeader(t) {
  const a = prog(t, 0, 1.2);
  text('GPU TRACEABILITY', 130, 104, 24, C.accent, '600', 'left', a, 'sans', 4);
  text('Identity is not location', 130, 168, 62, C.ink, '600', 'left', a);
  const b = prog(t, 0.8, 2.2);
  text('What the record leaves out', 132, 224, 30, C.muted, '400', 'left', b);
}

function drawCard(t) {
  const a = prog(t, 0.6, 2.0);
  const lift = (1 - a) * 14;
  ctx.save();
  ctx.globalAlpha *= a;
  ctx.translate(0, lift);

  ctx.fillStyle = C.surface;
  roundRect(CARD.x, CARD.y, CARD.w, CARD.h, 12); ctx.fill();
  ctx.strokeStyle = C.ink; ctx.lineWidth = 2.5;
  roundRect(CARD.x, CARD.y, CARD.w, CARD.h, 12); ctx.stroke();

  ctx.fillStyle = C.muted;
  for (let i = 0; i < 7; i++) ctx.fillRect(CARD.x + 24 + i * 9, CARD.y + 40, 4, 96);
  for (let i = 0; i < 7; i++) ctx.fillRect(CARD.x + CARD.w - 60 + i * 9, CARD.y + 40, 4, 96);

  ctx.fillStyle = C.ink;
  roundRect(CARD.x + 96, CARD.y + 40, 108, 96, 8); ctx.fill();
  text('H100', CARD.x + 150, CARD.y + 88, 28, C.white, '600', 'center', 1, 'mono');

  ctx.fillStyle = C.ink;
  ctx.fillRect(CARD.x + 24, CARD.y + 154, CARD.w - 48, 2);
  ctx.restore();

  const b = prog(t, 1.4, 2.6);
  ctx.save();
  ctx.globalAlpha *= a * b;
  ctx.translate(0, lift);
  text('SN 1037 8842 A', CARD.x + 4, CARD.y + CARD.h + 36, 22, C.ink, '500', 'left', 1, 'mono');
  text('one card', CARD.x + 4, CARD.y + CARD.h + 72, 24, C.muted, '400', 'left');
  ctx.restore();
}

function drawConnectors(t) {
  const a1 = prog(t, 2.6, 4.0);
  line(CARD.x + CARD.w + 8, CARD.y + 68, PANEL.x - 8, ROWS[0] + PANEL.h / 2, C.ink, a1, 2, [8, 6]);
  const a2 = prog(t, 7.2, 8.4);
  line(CARD.x + CARD.w + 8, CARD.y + 105, PANEL.x - 8, ROWS[1] + PANEL.h / 2, C.ink, a2, 2, [8, 6]);
  const a3 = prog(t, 11.8, 13.0);
  const late = prog(t, 17.2, 18.4);
  line(CARD.x + CARD.w + 8, CARD.y + 142, PANEL.x - 8, ROWS[2] + PANEL.h / 2,
       late > 0.5 ? C.red : C.ink, a3, late > 0.5 ? 3 : 2, [8, 6]);
}

function drawLayer1(t) {
  const a = prog(t, 2.4, 3.8);
  if (a <= 0) return;
  panel(PANEL.x, ROWS[0], PANEL.w, PANEL.h, a, false, false);
  text('LAYER 1  HARDWARE IDENTITY', PANEL.x + 44, ROWS[0] + 40, 21, C.muted, '600', 'left', a, 'sans', 2);
  text('Where the card came from, and who owns it', PANEL.x + 44, ROWS[0] + 80, 32, C.ink, '600', 'left', a);
  let x = PANEL.x + 44;
  const labels = ['serial number', 'manufacturing record', 'asset register', 'delivery record'];
  labels.forEach((l, i) => {
    const ca = prog(t, 3.4 + i * 0.35, 4.3 + i * 0.35);
    if (ca > 0) x += chip(l, x, ROWS[0] + 98, ca, C.blue) + 14;
  });
}

function drawLayer2(t) {
  const a = prog(t, 7.0, 8.4);
  if (a <= 0) return;
  panel(PANEL.x, ROWS[1], PANEL.w, PANEL.h, a, false, false);
  text('LAYER 2  OPERATING STATE', PANEL.x + 44, ROWS[1] + 40, 21, C.muted, '600', 'left', a, 'sans', 2);
  text('Telemetry, if the card sits on a management network', PANEL.x + 44, ROWS[1] + 80, 32, C.ink, '600', 'left', a);

  const metrics = [
    ['temp', '62 °C', 0.62],
    ['power', '684 W', 0.72],
    ['util', '91 %', 0.91],
  ];
  let x = PANEL.x + 44;
  metrics.forEach((m, i) => {
    const local = prog(t, 8.2 + i * 0.45, 9.4 + i * 0.45);
    if (local <= 0) return;
    const w = 200;
    ctx.save();
    ctx.globalAlpha *= a * local;
    ctx.fillStyle = C.surface; roundRect(x, ROWS[1] + 104, w, 26, 6); ctx.fill();
    ctx.fillStyle = C.teal; roundRect(x, ROWS[1] + 104, w * m[2] * local, 26, 6); ctx.fill();
    ctx.restore();
    text(m[1], x + w + 16, ROWS[1] + 117, 22, C.muted, '500', 'left', a * local, 'mono');
    text(m[0], x, ROWS[1] + 146, 18, C.muted, '400', 'left', a * local);
    x += w + 120;
  });
}

function drawLayer3(t) {
  const a = prog(t, 11.6, 13.0);
  if (a <= 0) return;
  const alert = prog(t, 17.2, 18.4);
  panel(PANEL.x, ROWS[2], PANEL.w, PANEL.h, a, alert > 0.4, true);
  text('LAYER 3  END USER AND END USE', PANEL.x + 44, ROWS[2] + 40, 21, C.muted, '600', 'left', a, 'sans', 2);
  text('Who submits the work, and what the work is for', PANEL.x + 44, ROWS[2] + 80, 32,
       alert > 0.5 ? C.red : C.ink, '600', 'left', a);

  const q = prog(t, 12.6, 14.0);
  ctx.save();
  ctx.globalAlpha *= q;
  ctx.strokeStyle = alert > 0.5 ? C.red : C.muted;
  ctx.lineWidth = 3; ctx.setLineDash([10, 8]);
  ctx.beginPath(); ctx.arc(PANEL.x + PANEL.w - 110, ROWS[2] + 72, 40, 0, Math.PI * 2); ctx.stroke();
  ctx.restore();
  text('?', PANEL.x + PANEL.w - 110, ROWS[2] + 74, 44, alert > 0.5 ? C.red : C.muted, '600', 'center', q);

  if (alert > 0) {
    text('no record links the card to the user', PANEL.x + 44, ROWS[2] + 132, 24, C.red, '600', 'left', prog(t, 18.4, 19.6));
    const w = 540 * ease(prog(t, 18.0, 19.2));
    ctx.save();
    ctx.globalAlpha *= alert;
    ctx.fillStyle = C.red;
    ctx.fillRect(PANEL.x + 44, ROWS[2] + 152, w, 2);
    ctx.restore();
  }
}

function drawFooter(t) {
  const a = prog(t, 20.4, 21.6);
  if (a <= 0) return;
  line(130, 800, 1790, 800, C.line, prog(t, 20.2, 21.4), 1.5);
  const words = ['Identify the card.', 'Locate the card.', 'Attribute the use.'];
  let x = 130;
  words.forEach((w, i) => {
    const la = prog(t, 20.8 + i * 0.5, 21.8 + i * 0.5);
    text(w, x, 858, 38, i === 2 ? C.accent : C.ink, '600', 'left', la);
    ctx.save();
    ctx.font = font('600', 38);
    x += ctx.measureText(w).width + 70;
    ctx.restore();
  });
}

function draw(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);
  drawHeader(t);
  drawConnectors(t);
  drawCard(t);
  drawLayer1(t);
  drawLayer2(t);
  drawLayer3(t);
  drawFooter(t);
}

window.DUR = DURATION;
window.seek = async (t) => { draw(Math.max(0, Math.min(DURATION, t))); };
draw(0);
document.fonts.ready.then(() => { window.READY = true; });
