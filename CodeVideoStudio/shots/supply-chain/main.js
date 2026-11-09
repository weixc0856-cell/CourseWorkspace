const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920, H = 1080, DURATION = 22;

const C = {
  bg: '#FBFAF7', ink: '#252A31', muted: '#6B7280', line: '#E3E0D7',
  surface: '#F3F1EA', accent: '#E8733B', blue: '#4A82B8', teal: '#42A69A',
  purple: '#7A6FB0', red: '#C75B55', white: '#FFFFFF',
};

const clamp01 = (x) => Math.max(0, Math.min(1, x));
const ease = (x) => { const v = clamp01(x); return v * v * (3 - 2 * v); };
const prog = (t, a, b) => ease((t - a) / (b - a));
const font = (w, s) => `${w} ${s}px "Segoe UI", Aptos, Helvetica, Arial, sans-serif`;

function text(str, x, y, size, color, weight = '400', align = 'left', alpha = 1, tracking = 0) {
  ctx.save();
  ctx.globalAlpha *= alpha;
  ctx.fillStyle = color;
  ctx.font = font(weight, size);
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

const NW = 260, NH = 150, NY = 320, GAP = 110;
const NODES = [
  { name: 'Chip designer', knows: 'model, serial, licence' },
  { name: 'Server OEM', knows: 'build, ship-to address' },
  { name: 'Data centre', knows: 'power, capacity, tenants' },
  { name: 'Cloud provider', knows: 'accounts, API calls' },
  { name: 'End customer', knows: 'intent and identity' },
];
NODES.forEach((n, i) => { n.x = 90 + i * (NW + GAP); n.y = NY; });

function drawHeader(t) {
  const a = prog(t, 0, 1.2);
  text('THE CHAIN', 90, 104, 24, C.accent, '600', 'left', a, 4);
  text('Five hands, five partial views', 90, 168, 60, C.ink, '600', 'left', a);
  text('Who can see what about a single card', 92, 222, 28, C.muted, '400', 'left', prog(t, 0.7, 1.9));
}

function drawNodes(t) {
  NODES.forEach((n, i) => {
    const a = prog(t, 2.2 + i * 0.55, 3.3 + i * 0.55);
    if (a <= 0) return;
    const last = i === NODES.length - 1;
    const dy = (1 - a) * 16;
    ctx.save();
    ctx.translate(0, dy);
    ctx.globalAlpha *= a;
    ctx.fillStyle = last ? C.white : C.white;
    roundRect(n.x, n.y, NW, NH, 12); ctx.fill();
    ctx.strokeStyle = last ? C.accent : C.ink;
    ctx.lineWidth = last ? 2.5 : 2;
    if (last) ctx.setLineDash([12, 9]);
    roundRect(n.x, n.y, NW, NH, 12); ctx.stroke();
    ctx.restore();

    text(`0${i + 1}`, n.x + 28, n.y + 40, 20, C.muted, '600', 'left', a, 2);
    text(n.name, n.x + 28, n.y + 82, 30, last ? C.accent : C.ink, '600', 'left', a);
    text(n.knows, n.x + 28, n.y + 120, 21, C.muted, '400', 'left', a);

    if (i < NODES.length - 1) {
      const ax = n.x + NW + 18, ay = n.y + NH / 2;
      const aa = prog(t, 2.8 + i * 0.55, 3.7 + i * 0.55);
      ctx.save();
      ctx.globalAlpha *= aa;
      ctx.strokeStyle = C.muted; ctx.lineWidth = 2; ctx.setLineDash([6, 6]);
      ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(ax + GAP - 46, ay); ctx.stroke();
      ctx.fillStyle = C.muted;
      ctx.beginPath();
      ctx.moveTo(ax + GAP - 26, ay);
      ctx.lineTo(ax + GAP - 46, ay - 9);
      ctx.lineTo(ax + GAP - 46, ay + 9);
      ctx.closePath(); ctx.fill();
      ctx.restore();
    }
  });
}

function drawCoverage(t) {
  const a = prog(t, 12.4, 13.8);
  if (a <= 0) return;
  const y = 616;
  text('WHO IS IN THE DUE-DILIGENCE CHAIN', 90, y - 34, 20, C.muted, '600', 'left', a, 2);

  const fullEnd = NODES[3].x + NW;
  const drawX = 90 + (fullEnd - 90) * ease(prog(t, 12.8, 15.4));
  ctx.save();
  ctx.globalAlpha *= a;
  ctx.fillStyle = C.teal;
  roundRect(90, y + 6, Math.max(8, drawX - 90), 26, 6); ctx.fill();
  ctx.restore();

  const lastStart = NODES[4].x;
  text('covered', 90, y + 66, 21, C.teal, '600', 'left', a);

  const b = prog(t, 15.2, 16.4);
  if (b > 0) {
    ctx.save();
    ctx.globalAlpha *= b;
    ctx.strokeStyle = C.red; ctx.lineWidth = 2.5; ctx.setLineDash([10, 8]);
    roundRect(lastStart, y + 6, NW, 26, 6); ctx.stroke();
    ctx.restore();
    text('the last mile', lastStart, y + 66, 21, C.red, '600', 'left', b);
  }
}

function drawClosing(t) {
  const a = prog(t, 16.6, 18.0);
  if (a <= 0) return;
  const rule = prog(t, 16.4, 17.6);
  ctx.save();
  ctx.globalAlpha *= rule;
  ctx.fillStyle = C.line;
  ctx.fillRect(90, 742, 1740 * rule, 2);
  ctx.restore();

  text('Every hand sees a slice.', 90, 790, 38, C.ink, '600', 'left', prog(t, 17.0, 18.2));
  text('No hand sees the whole card.', 90, 836, 38, C.muted, '600', 'left', prog(t, 17.6, 18.8));

  const c = prog(t, 18.6, 20.0);
  if (c > 0) {
    text('Reviewing the customer is the only point where a card becomes a person.', 90, 890, 28, C.accent, '500', 'left', c);
  }
}

function draw(t) {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalAlpha = 1;
  ctx.fillStyle = C.bg;
  ctx.fillRect(0, 0, W, H);
  drawHeader(t);
  drawNodes(t);
  drawCoverage(t);
  drawClosing(t);
}

window.DUR = DURATION;
window.seek = async (t) => { draw(Math.max(0, Math.min(DURATION, t))); };
draw(0);
document.fonts.ready.then(() => { window.READY = true; });
