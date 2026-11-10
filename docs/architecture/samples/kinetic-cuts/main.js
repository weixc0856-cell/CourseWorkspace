// Validation sample 2: kinetic editing, 12 s, four 3 s hard-cut shots.
// Every pixel is a pure function of t. No wall clock, no unseeded randomness.
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');

window.DUR = 12;

const W = 1920, H = 1080;
const INK = '#1D1B17', MUTED = '#7C756B', ACCENT = '#D97757', TEAL = '#4C7A6A';
const PAPER = '#F6F1E7', GRID = '#E7DFD0';
const FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif';

const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
const ease = t => 1 - Math.pow(1 - clamp(t), 3);
const pulse = (t, at, width = 0.28) => {
  const d = Math.abs(t - at) / width;
  return d >= 1 ? 0 : 1 - d;
};

function drawGrid() {
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = GRID;
  ctx.lineWidth = 1;
  for (let x = 80; x < W; x += 80) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
  }
  for (let y = 80; y < H; y += 80) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
  }
}

function drawChrome(shotIndex) {
  ctx.save();
  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = MUTED;
  ctx.textAlign = 'left';
  ctx.fillText(`0${shotIndex + 1} · 原理`, 96, 92);
  ctx.textAlign = 'right';
  ctx.fillStyle = INK;
  ctx.fillText('WORKSPACE', W - 96, 92);
  // small mark
  ctx.fillStyle = ACCENT;
  ctx.fillRect(W - 96 - 190, 74, 18, 18);
  ctx.restore();
}

function measure(text, size, weight = 700) {
  ctx.font = `${weight} ${size}px ${FONT}`;
  return ctx.measureText(text).width;
}

function word(text, x, y, size, color, alpha = 1, weight = 700) {
  if (alpha <= 0) return;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = color;
  ctx.font = `${weight} ${size}px ${FONT}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
  ctx.restore();
}

function shotOne(t) {
  const line1 = [
    { text: '配音', at: 0.10, size: 112 },
    { text: '是', at: 0.32, size: 78 },
    { text: '整条视频的', at: 0.54, size: 104 },
  ];
  const gap = 34;
  const widths = line1.map(w => measure(w.text, w.size));
  const total1 = widths.reduce((a, b) => a + b, 0) + gap * (line1.length - 1);
  let x = W / 2 - total1 / 2;
  line1.forEach((w, i) => {
    const a = ease((t - w.at) / 0.16);
    const dy = (1 - a) * 46;
    word(w.text, x + widths[i] / 2, 480 + dy, w.size, INK, a);
    x += widths[i] + gap;
  });
  const a2 = ease((t - 0.78) / 0.18);
  word('时钟', W / 2, 650 + (1 - a2) * 46, 136, ACCENT, a2);
  const u = ease((t - 0.98) / 0.18);
  if (u > 0) {
    const w = 210 * u;
    ctx.fillStyle = ACCENT;
    ctx.fillRect(W / 2 - w / 2, 742, w, 10);
  }
  const c = ease((t - 0.15) / 0.6);
  ctx.save();
  ctx.globalAlpha = 0.5;
  ctx.strokeStyle = MUTED;
  ctx.lineWidth = 3;
  for (let i = 0; i < 12; i++) {
    const ang = (i / 12) * Math.PI * 2 - Math.PI / 2;
    const r1 = 250, r2 = 250 + 18 * c;
    ctx.beginPath();
    ctx.moveTo(W / 2 + Math.cos(ang) * r1, 540 + Math.sin(ang) * r1);
    ctx.lineTo(W / 2 + Math.cos(ang) * r2, 540 + Math.sin(ang) * r2);
    ctx.stroke();
  }
  ctx.restore();
}

function shotTwo(t) {
  const line = '每一个字，都有它自己的时间';
  const size = 96;
  const chars = [...line];
  const total = measure(line, size);
  const left = W / 2 - total / 2;
  const p = clamp((t - 0.5) / 1.8);
  const bandX = left + total * p;
  ctx.save();
  ctx.fillStyle = ACCENT;
  ctx.globalAlpha = 0.9;
  ctx.fillRect(bandX - 46, 440, 92, 128);
  ctx.restore();
  let x = left;
  const start = 0.06;
  chars.forEach((ch, i) => {
    const a = ease((t - start - i * 0.055) / 0.12);
    ctx.save();
    ctx.globalAlpha = a;
    ctx.font = `700 ${size}px ${FONT}`;
    ctx.textBaseline = 'middle';
    ctx.fillStyle = INK;
    ctx.fillText(ch, x, 500);
    ctx.restore();
    x += ctx.measureText(ch).width;
  });
}

function shotThree(t) {
  const a1 = ease((t - 0.05) / 0.16);
  const a2 = ease((t - 0.26) / 0.16);
  word('画面', W / 2, 470, 120, INK, a1);
  const scale = 1 + 0.06 * pulse(t, 0.95, 0.32);
  ctx.save();
  ctx.translate(W / 2, 620);
  ctx.scale(scale, scale);
  ctx.globalAlpha = a2;
  ctx.fillStyle = ACCENT;
  ctx.font = `700 152px ${FONT}`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('卡在词上', 0, 0);
  ctx.restore();
  // playhead sweeps across the word
  const p = clamp((t - 0.55) / 1.4);
  const x = W / 2 - 300 + 600 * p;
  ctx.save();
  ctx.strokeStyle = TEAL;
  ctx.lineWidth = 4;
  ctx.beginPath(); ctx.moveTo(x, 520); ctx.lineTo(x, 760); ctx.stroke();
  ctx.fillStyle = TEAL;
  ctx.beginPath(); ctx.moveTo(x, 520); ctx.lineTo(x + 22, 506); ctx.lineTo(x + 22, 534); ctx.closePath(); ctx.fill();
  ctx.restore();
}

function shotFour(t) {
  const a = ease((t - 0.05) / 0.16);
  word('所以不会错位', W / 2, 500, 120, INK, a);
  // three bars snap into alignment
  const bars = [
    { y: 650, target: 0.0 },
    { y: 720, target: 0.0 },
    { y: 790, target: 0.0 },
  ];
  bars.forEach((b, i) => {
    const snap = ease((t - 0.45 - i * 0.12) / 0.22);
    const off = (1 - snap) * (i === 0 ? -180 : i === 1 ? -90 : 60);
    const w = 620 * ease((t - 0.2 - i * 0.08) / 0.3);
    ctx.save();
    ctx.fillStyle = i === 1 ? ACCENT : TEAL;
    ctx.globalAlpha = 0.85;
    ctx.fillRect(W / 2 - 310 + off, b.y, w, 26);
    ctx.restore();
  });
  // check mark
  const c = ease((t - 1.15) / 0.35);
  if (c > 0) {
    ctx.save();
    ctx.strokeStyle = ACCENT;
    ctx.lineWidth = 10;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(W - 330, 300);
    ctx.lineTo(W - 300 + 32 * c, 300 + 40 * c);
    ctx.lineTo(W - 300 + 92 * c, 300 - 40 * c);
    ctx.stroke();
    ctx.restore();
  }
}

const shots = [shotOne, shotTwo, shotThree, shotFour];

window.seek = async t => {
  drawGrid();
  const index = Math.min(3, Math.floor(t / 3));
  const local = t - index * 3;
  drawChrome(index);
  shots[index](local);
};

window.READY = true;
