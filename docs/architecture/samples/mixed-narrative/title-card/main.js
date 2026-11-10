const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const W = 1920, H = 1080;
window.DUR = 3;
const INK = '#1D1B17', MUTED = '#7C756B', ACCENT = '#D97757', TEAL = '#4C7A6A', PAPER = '#F6F1E7';
const FONT = '"Microsoft YaHei", "PingFang SC", "Noto Sans SC", sans-serif';
const ease = t => 1 - Math.pow(1 - Math.max(0, Math.min(1, t)), 3);

window.seek = async t => {
  ctx.fillStyle = PAPER; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = '#E7DFD0'; ctx.lineWidth = 1;
  for (let x = 80; x < W; x += 80) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = 80; y < H; y += 80) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
  const a = ease(t / 0.5);
  ctx.globalAlpha = a;
  ctx.fillStyle = INK; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.font = `700 104px ${FONT}`;
  ctx.fillText('一条时间线，四种语法', W / 2, 480);
  ctx.globalAlpha = ease((t - 0.35) / 0.4);
  ctx.font = `400 34px ${FONT}`; ctx.fillStyle = MUTED;
  ctx.fillText('长镜头 · 快切 · 模拟 · 动态文字', W / 2, 590);
  const tags = [['长镜头', TEAL, 0.45], ['快切', ACCENT, 0.62], ['模拟', TEAL, 0.79]];
  tags.forEach(([label, color, at], i) => {
    const p = ease((t - at) / 0.25);
    ctx.globalAlpha = p;
    const x = W / 2 - 300 + i * 220;
    ctx.fillStyle = color;
    ctx.fillRect(x, 690, 10, 34);
    ctx.fillStyle = INK; ctx.font = `700 32px ${FONT}`; ctx.textAlign = 'left';
    ctx.fillText(label, x + 24, 707);
  });
  ctx.globalAlpha = 1;
};
window.READY = true;
