const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920;
const H = 1080;

const C = {
  bg: '#FBFAF7',
  ink: '#1A1A1A',
  muted: '#595959',
  line: '#D8D4CC',
  orange: '#EB6100',
  orangeSoft: '#FFF1E8',
  blue: '#2F6DB3',
  green: '#2F8F6B',
  magenta: '#B3478A',
  white: '#FFFFFF',
};

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => {
  const v = clamp01(x);
  return v * v * (3 - 2 * v);
};
const progress = (t, start, end) => ease((t - start) / (end - start));
const font = (weight, size) => `${weight} ${size}px "Segoe UI", Arial, sans-serif`;

function roundRect(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function label(text, x, y, size, color, weight = '400', align = 'left', alpha = 1) {
  ctx.save();
  const inherited = ctx.globalAlpha;
  ctx.globalAlpha = inherited * alpha;
  ctx.fillStyle = color;
  ctx.font = font(weight, size);
  ctx.textAlign = align;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
  ctx.restore();
}

function arrow(x1, y1, x2, y2, color, alpha, width = 3) {
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = 'round';
  const angle = Math.atan2(y2 - y1, x2 - x1);
  const head = 14;
  const endX = x2 - Math.cos(angle) * head * 0.6;
  const endY = y2 - Math.sin(angle) * head * 0.6;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(endX, endY);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x2, y2);
  ctx.lineTo(x2 - Math.cos(angle - 0.42) * head, y2 - Math.sin(angle - 0.42) * head);
  ctx.lineTo(x2 - Math.cos(angle + 0.42) * head, y2 - Math.sin(angle + 0.42) * head);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

const TOKENS = ['The', 'animal', "didn't", 'cross', 'street'];
const SCORES = [0.22, 0.42, 0.12, 0.28, 0.55];
const TOKEN_BOX_W = 170;
const TOKEN_BOX_H = 92;
const TOKEN_GAP = 14;
const TOKEN_TOTAL = TOKENS.length * TOKEN_BOX_W + (TOKENS.length - 1) * TOKEN_GAP;
const TOKEN_START = (1100 - TOKEN_TOTAL) / 2;
const TOKEN_Y = 280;

function tokenX(index) {
  return TOKEN_START + index * (TOKEN_BOX_W + TOKEN_GAP);
}

function drawBackground(t) {
  ctx.save();
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = C.orange;
  ctx.fillRect(0, 0, W, 12);
  ctx.restore();
}

function drawTitle(t) {
  const alpha = progress(t, 0.2, 1.0);
  label('Self-attention in one pass', 140, 92, 64, C.ink, '700', 'left', alpha);
  label('Each token asks every token what it needs.', 142, 156, 30, C.muted, '400', 'left', alpha);
}

function drawTokens(t) {
  const alpha = progress(t, 3.0, 3.9);
  const highlight = progress(t, 5.0, 5.7);
  TOKENS.forEach((token, index) => {
    const x = tokenX(index);
    const pulse = index === 1 && t > 5 ? 1.5 * Math.sin((t - 5) * 2.0) : 0;
    const y = TOKEN_Y - (index === 1 ? 5 * highlight : 0) + pulse;
    ctx.save();
    ctx.globalAlpha = alpha;
    roundRect(x, y, TOKEN_BOX_W, TOKEN_BOX_H, 14);
    ctx.fillStyle = index === 1 ? C.orangeSoft : C.white;
    ctx.fill();
    ctx.lineWidth = index === 1 ? 3 : 2;
    ctx.strokeStyle = index === 1 ? C.orange : C.line;
    ctx.stroke();
    label(token, x + TOKEN_BOX_W / 2, y + TOKEN_BOX_H / 2, 26, index === 1 ? C.ink : C.muted, index === 1 ? '700' : '500', 'center');
    ctx.restore();
  });
  const animalX = tokenX(1) + TOKEN_BOX_W / 2;
  const animalY = TOKEN_Y + TOKEN_BOX_H;
  if (highlight > 0) {
    label('focus', animalX, TOKEN_Y - 38, 20, C.orange, '700', 'center', highlight);
    ctx.save();
    ctx.globalAlpha = highlight;
    ctx.strokeStyle = C.orange;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(animalX, animalY + 12);
    ctx.lineTo(animalX, animalY + 34);
    ctx.stroke();
    ctx.restore();
  }
}

function drawProjections(t) {
  const alpha = progress(t, 8.5, 9.4);
  const dim = 1 - 0.55 * progress(t, 23.0, 23.8);
  const boxes = [
    { name: 'Query', color: C.blue, x: 210 },
    { name: 'Key', color: C.green, x: 510 },
    { name: 'Value', color: C.magenta, x: 810 },
  ];
  const boxY = 520;
  const boxW = 240;
  const boxH = 118;
  const animalX = tokenX(1) + TOKEN_BOX_W / 2;
  const animalY = TOKEN_Y + TOKEN_BOX_H;

  boxes.forEach((box) => {
    arrow(animalX, animalY + 38, box.x + boxW / 2, boxY - 8, C.line, alpha * dim, 3);
    ctx.save();
    ctx.globalAlpha = alpha * dim;
    roundRect(box.x, boxY, boxW, boxH, 14);
    ctx.fillStyle = C.white;
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = box.color;
    ctx.stroke();
    label(box.name, box.x + boxW / 2, boxY + 42, 30, box.color, '700', 'center');
    label('projection', box.x + boxW / 2, boxY + 82, 20, C.muted, '400', 'center');
    ctx.restore();
  });
}

function drawScores(t) {
  const panelAlpha = progress(t, 15.0, 15.8);
  const dim = 1 - 0.55 * progress(t, 23.0, 23.8);
  const panelX = 1120;
  const panelY = 292;
  const panelW = 680;
  const panelH = 440;

  ctx.save();
  ctx.globalAlpha = panelAlpha * dim;
  roundRect(panelX, panelY, panelW, panelH, 18);
  ctx.fillStyle = C.white;
  ctx.fill();
  ctx.lineWidth = 2;
  ctx.strokeStyle = C.line;
  ctx.stroke();
  ctx.restore();

  label('attention scores for “animal”', panelX + 34, panelY + 44, 28, C.ink, '600', 'left', panelAlpha * dim);
  label('schematic — not measured weights', panelX + 34, panelY + 78, 18, C.muted, '400', 'left', panelAlpha * dim * 0.9);

  const baseY = panelY + 350;
  const maxHeight = 215;
  const barW = 86;
  const gap = 32;
  const startX = panelX + 46;
  TOKENS.forEach((token, index) => {
    const grow = progress(t, 15.2 + index * 0.18, 16.4 + index * 0.18);
    const value = SCORES[index];
    const height = maxHeight * value * grow;
    const x = startX + index * (barW + gap);
    ctx.save();
    ctx.globalAlpha = panelAlpha * dim;
    ctx.fillStyle = '#F1EDE6';
    roundRect(x, baseY - maxHeight, barW, maxHeight, 8);
    ctx.fill();
    ctx.fillStyle = index === 4 ? C.orange : index === 1 ? '#F2A46F' : '#F7C9A8';
    if (height > 0.5) {
      roundRect(x, baseY - height, barW, height, 8);
      ctx.fill();
    }
    label(token, x + barW / 2, baseY + 26, 18, index === 4 || index === 1 ? C.ink : C.muted, index === 4 ? '700' : '400', 'center');
    ctx.restore();
  });
}

function drawContext(t) {
  const alpha = progress(t, 23.0, 23.9);
  const x = 1290;
  const y = 798;
  const w = 360;
  const h = 112;
  arrow(1500, 742, 1470, y - 8, C.orange, alpha, 3);
  ctx.save();
  ctx.globalAlpha = alpha;
  roundRect(x, y, w, h, 16);
  ctx.fillStyle = C.ink;
  ctx.fill();
  ctx.lineWidth = 3;
  ctx.strokeStyle = C.orange;
  ctx.stroke();
  label('context vector', x + w / 2, y + 42, 28, C.white, '700', 'center');
  label('weighted sum of V', x + w / 2, y + 78, 18, '#D8D4CC', '400', 'center');
  ctx.restore();
}

function drawSummary(t) {
  const alpha = progress(t, 28.0, 28.8);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = C.orange;
  ctx.beginPath();
  ctx.arc(150, 850, 6, 0, Math.PI * 2);
  ctx.fill();
  label('Q · K decide where to look', 172, 850, 30, C.ink, '600');
  ctx.fillStyle = C.orange;
  ctx.beginPath();
  ctx.arc(150, 902, 6, 0, Math.PI * 2);
  ctx.fill();
  label('V is what gets passed back', 172, 902, 30, C.ink, '600');
  ctx.restore();
}

function drawProgress(t) {
  const x = 140;
  const y = 1012;
  const w = 1640;
  ctx.save();
  ctx.fillStyle = C.line;
  ctx.fillRect(x, y, w, 3);
  ctx.fillStyle = C.orange;
  ctx.fillRect(x, y, w * clamp01(t / 30), 3);
  const seconds = Math.min(30, Math.floor(t));
  label(`00:${String(seconds).padStart(2, '0')} / 00:30`, W - 140, y, 18, C.muted, '400', 'right');
  ctx.restore();
}

function draw(t) {
  drawBackground(t);
  drawTitle(t);
  drawTokens(t);
  drawProjections(t);
  drawScores(t);
  drawContext(t);
  drawSummary(t);
  drawProgress(t);
}

window.DUR = 30;
window.seek = async (t) => {
  draw(Math.max(0, Math.min(30, t)));
};
draw(0);
document.fonts.ready.then(() => {
  window.READY = true;
});
