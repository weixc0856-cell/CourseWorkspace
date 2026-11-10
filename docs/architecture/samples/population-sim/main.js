// Validation sample 3: deterministic population simulation (SIR), 12 s.
// The whole film is precomputed once at load; seek(t) only reads a frame.
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920, H = 1080;
const FPS = 30, DUR = 12, FRAMES = DUR * FPS + 1;

window.DUR = DUR;

const PAPER = '#F6F1E7', INK = '#1D1B17', MUTED = '#7C756B';
const S_COLOR = '#A7A198', I_COLOR = '#D97757', R_COLOR = '#4C7A6A';
const FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif';

const WORLD = { x: 260, y: 230, w: 1080, h: 620 };
const AGENTS = 240;
const RADIUS = 34;
const INFECT_P = 0.18;
const RECOVER_FRAMES = 110;

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const rand = mulberry32(20261109);
const agents = [];
for (let i = 0; i < AGENTS; i++) {
  agents.push({
    x: WORLD.x + rand() * WORLD.w,
    y: WORLD.y + rand() * WORLD.h,
    vx: (rand() - 0.5) * 66,
    vy: (rand() - 0.5) * 66,
    state: 0, // 0 S, 1 I, 2 R
    infectedAt: -1,
  });
}
// Three patient zeros near the centre.
for (let i = 0; i < 3; i++) {
  const patient = agents[i];
  patient.x = WORLD.x + WORLD.w * (0.48 + i * 0.025);
  patient.y = WORLD.y + WORLD.h * (0.46 + (i % 2) * 0.03);
  patient.state = 1;
  patient.infectedAt = 0;
}

const frames = [];

function step(frameIndex) {
  const dt = 1 / FPS;
  // move
  for (const a of agents) {
    if (a.state === 2) {
      a.vx *= 0.999;
      a.vy *= 0.999;
    }
    a.x += a.vx * dt;
    a.y += a.vy * dt;
    if (a.x < WORLD.x + 8 || a.x > WORLD.x + WORLD.w - 8) { a.vx *= -1; a.x = Math.max(WORLD.x + 8, Math.min(WORLD.x + WORLD.w - 8, a.x)); }
    if (a.y < WORLD.y + 8 || a.y > WORLD.y + WORLD.h - 8) { a.vy *= -1; a.y = Math.max(WORLD.y + 8, Math.min(WORLD.y + WORLD.h - 8, a.y)); }
  }
  // recover
  for (const a of agents) {
    if (a.state === 1 && frameIndex - a.infectedAt >= RECOVER_FRAMES) a.state = 2;
  }
  // infect (deterministic: same rand sequence every run)
  const infected = agents.filter(a => a.state === 1);
  for (const src of infected) {
    for (const dst of agents) {
      if (dst.state !== 0) continue;
      const dx = src.x - dst.x, dy = src.y - dst.y;
      if (dx * dx + dy * dy < RADIUS * RADIUS && rand() < INFECT_P) {
        dst.state = 1;
        dst.infectedAt = frameIndex;
      }
    }
  }
  let s = 0, i = 0, r = 0;
  for (const a of agents) (a.state === 0 ? s++ : a.state === 1 ? i++ : r++);
  return { s, i, r };
}

for (let f = 0; f < FRAMES; f++) {
  const counts = step(f);
  frames.push({
    agents: agents.map(a => ({ x: a.x, y: a.y, state: a.state })),
    counts,
  });
}

function drawBackground() {
  ctx.fillStyle = PAPER;
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#E7DFD0';
  ctx.lineWidth = 1;
  for (let x = 80; x < W; x += 80) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 80; y < H; y += 80) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  ctx.strokeStyle = '#D9D1C3';
  ctx.lineWidth = 2;
  ctx.strokeRect(WORLD.x, WORLD.y, WORLD.w, WORLD.h);
}

function drawChrome(frame) {
  ctx.save();
  ctx.font = `600 24px ${FONT}`;
  ctx.fillStyle = MUTED;
  ctx.textAlign = 'left';
  ctx.fillText('01 · 模拟', 96, 92);
  ctx.textAlign = 'right';
  ctx.fillStyle = INK;
  ctx.fillText('WORKSPACE', W - 96, 92);
  ctx.fillStyle = I_COLOR;
  ctx.fillRect(W - 96 - 190, 74, 18, 18);
  ctx.restore();
}

function drawTitle() {
  ctx.save();
  ctx.fillStyle = INK;
  ctx.font = `700 56px ${FONT}`;
  ctx.textAlign = 'left';
  ctx.fillText('感染在接触中传播', WORLD.x, 150);
  ctx.fillStyle = MUTED;
  ctx.font = `400 28px ${FONT}`;
  ctx.fillText('SIR · 240 个体 · 固定种子 20261109', WORLD.x, 192);
  ctx.restore();
}

function drawCounts(counts) {
  const x = W - 360;
  const rows = [
    ['易感', counts.s, S_COLOR],
    ['感染', counts.i, I_COLOR],
    ['恢复', counts.r, R_COLOR],
  ];
  ctx.save();
  rows.forEach(([label, value, color], i) => {
    const y = 150 + i * 56;
    ctx.fillStyle = color;
    ctx.fillRect(x - 18, y - 30, 10, 38);
    ctx.fillStyle = MUTED;
    ctx.font = `400 24px ${FONT}`;
    ctx.textAlign = 'left';
    ctx.fillText(label, x, y);
    ctx.fillStyle = INK;
    ctx.font = `700 40px ${FONT}`;
    ctx.textAlign = 'right';
    ctx.fillText(String(value), W - 96, y);
  });
  ctx.restore();
}

function drawAgents(state) {
  for (const a of state.agents) {
    ctx.beginPath();
    ctx.fillStyle = a.state === 0 ? S_COLOR : a.state === 1 ? I_COLOR : R_COLOR;
    ctx.arc(a.x, a.y, a.state === 1 ? 5.4 : 4.6, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawCurve(frame) {
  const box = { x: WORLD.x, y: WORLD.y + WORLD.h + 38, w: WORLD.w, h: 100 };
  ctx.save();
  ctx.strokeStyle = '#D9D1C3';
  ctx.lineWidth = 1;
  ctx.strokeRect(box.x, box.y, box.w, box.h);
  ctx.beginPath();
  ctx.strokeStyle = I_COLOR;
  ctx.lineWidth = 4;
  for (let f = 0; f <= frame; f++) {
    const p = f / (FRAMES - 1);
    const v = frames[f].counts.i / AGENTS;
    const x = box.x + p * box.w;
    const y = box.y + box.h - v * box.h;
    if (f === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
  const now = frames[frame].counts.i / AGENTS;
  ctx.fillStyle = I_COLOR;
  ctx.beginPath();
  ctx.arc(box.x + (frame / (FRAMES - 1)) * box.w, box.y + box.h - now * box.h, 6, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = MUTED;
  ctx.font = `400 22px ${FONT}`;
  ctx.textAlign = 'left';
  ctx.fillText('感染比例', box.x, box.y + box.h + 32);
  ctx.restore();
}

window.seek = async t => {
  const frame = Math.max(0, Math.min(FRAMES - 1, Math.round(t * FPS)));
  drawBackground();
  drawChrome(frame);
  drawTitle();
  drawCounts(frames[frame].counts);
  drawAgents(frames[frame]);
  drawCurve(frame);
};

window.READY = true;
