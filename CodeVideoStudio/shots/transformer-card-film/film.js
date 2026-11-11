// Transformer — card film. 24 cards / 180 s / hard cuts.
// Data in cards.json; every frame is a pure function of t.
(() => {
  const W = 1920, H = 1080, FPS = 30;
  const NUM_FONT = 'Jost, "Noto Sans SC", sans-serif';
  const CN_FONT = '"Noto Sans SC", "Microsoft YaHei", sans-serif';

  const THEMES = {
    dark: {
      bg: '#0A0908', text: '#F4F1EA', body: '#E4DFD4', muted: '#9A917F',
      accent: '#E8A33D', accentHot: '#FFC46B', border: 'rgba(244,241,234,0.16)',
      wash0: 'rgba(48,26,10,0.30)', wash1: 'rgba(18,11,7,0.42)',
      shaft: 'rgba(255,246,230,', shaftA: 0.10, core: 'rgba(255,236,200,0.10)',
      dust: 'rgba(255,214,150,', grain: 0.05, vignette: 'rgba(0,0,0,0.82)',
      gold: ['#FFCE6E', '#FFA838', '#E07A21', '#8C3D07'],
    },
    light: {
      bg: '#FBFAF7', text: '#252A31', body: '#2E3338', muted: '#6B7280',
      accent: '#D9662B', accentHot: '#E8733B', border: 'rgba(37,42,49,0.18)',
      wash0: 'rgba(232,115,59,0.05)', wash1: 'rgba(214,200,176,0.22)',
      shaft: 'rgba(255,252,244,', shaftA: 0.55, core: 'rgba(255,255,255,0.45)',
      dust: 'rgba(214,164,110,', grain: 0.04, vignette: 'rgba(90,74,56,0.16)',
      gold: ['#F5915C', '#E8733B', '#C9551E', '#93380D'],
    },
  };

  const cv = document.getElementById('c');
  const ctx = cv.getContext('2d');
  let D = THEMES.dark;
  let cards = [];
  let DUR = 180;

  // ---------- math ----------
  const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
  const span = (t, a, b) => clamp01((t - a) / (b - a));
  const easeOut = (p) => 1 - Math.pow(1 - p, 3);
  const easeInOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
  const lerp = (a, b, p) => a + (b - a) * p;
  const hash = (n) => {
    const s = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return s - Math.floor(s);
  };

  // ---------- ground ----------
  function field(t) {
    ctx.fillStyle = D.bg;
    ctx.fillRect(0, 0, W, H);
    const shaftX = 760 + Math.sin(t * 0.07) * 90;
    const g = ctx.createRadialGradient(shaftX, H * 0.55, 40, shaftX, H * 0.55, 820);
    g.addColorStop(0, D.wash0);
    g.addColorStop(0.45, D.wash1);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);

    ctx.save();
    const lg = ctx.createLinearGradient(shaftX - 190, 0, shaftX + 190, 0);
    lg.addColorStop(0, D.shaft + '0)');
    lg.addColorStop(0.36, `${D.shaft}${0.10 * D.shaftA * 4})`);
    lg.addColorStop(0.5, `${D.shaft}${0.30 * D.shaftA * 4})`);
    lg.addColorStop(0.64, `${D.shaft}${0.10 * D.shaftA * 4})`);
    lg.addColorStop(1, D.shaft + '0)');
    ctx.fillStyle = lg;
    ctx.fillRect(shaftX - 190, 0, 380, H);
    ctx.fillStyle = D.core;
    ctx.fillRect(shaftX - 1.2, 0, 2.4, H);
    ctx.restore();

    ctx.save();
    for (let i = 0; i < 80; i++) {
      const x = shaftX + (hash(i * 7.1) - 0.5) * 560;
      const y = ((hash(i * 11.7) * H + t * (10 + hash(i * 3.3) * 34)) % (H + 120)) - 60;
      ctx.fillStyle = `${D.dust}${(0.05 + 0.15 * hash(i * 5.9)) * (0.5 + 0.5 * Math.sin(t * 0.7 + i))})`;
      ctx.beginPath();
      ctx.arc(x + Math.sin(t * 0.4 + i) * 6, y, 0.8 + hash(i * 3.3) * 1.5, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function overlay(t) {
    const vg = ctx.createRadialGradient(W * 0.5, H * 0.5, H * 0.3, W * 0.5, H * 0.5, H * 0.95);
    vg.addColorStop(0, 'rgba(0,0,0,0)');
    vg.addColorStop(1, D.vignette);
    ctx.fillStyle = vg;
    ctx.fillRect(0, 0, W, H);
    const seed = Math.floor(t * FPS);
    ctx.save();
    ctx.globalAlpha = D.grain;
    for (let i = 0; i < 1100; i++) {
      const x = hash(seed * 131 + i) * W;
      const y = hash(seed * 197 + i * 7) * H;
      ctx.fillStyle = D === THEMES.dark
        ? (hash(i) > 0.5 ? '#ffffff' : '#000000')
        : 'rgba(42,47,54,0.05)';
      ctx.fillRect(x, y, 1.2, 1.2);
    }
    ctx.restore();
  }

  // ---------- type ----------
  const goldFill = (x, y, size) => {
    const g = ctx.createLinearGradient(x, y - size, x + size * 0.7, y);
    g.addColorStop(0, D.gold[0]);
    g.addColorStop(0.3, D.gold[1]);
    g.addColorStop(0.68, D.gold[2]);
    g.addColorStop(1, D.gold[3]);
    return g;
  };

  function label(txt, x, y, alpha) {
    ctx.save();
    ctx.font = `300 21px ${NUM_FONT}`;
    ctx.fillStyle = D.accent;
    ctx.globalAlpha = 0.85 * alpha;
    if ('letterSpacing' in ctx) ctx.letterSpacing = '6px';
    ctx.fillText(txt, x, y);
    ctx.restore();
  }

  function wrap(text, maxW, font) {
    ctx.font = font;
    const lines = [];
    let line = '';
    for (const ch of text) {
      const next = line + ch;
      if (ctx.measureText(next).width > maxW && line) {
        lines.push(line);
        line = ch;
      } else {
        line = next;
      }
    }
    if (line) lines.push(line);
    return lines;
  }

  // ---------- kinds ----------
  function drawFigure(card, u, A) {
    const baseY = 700;
    let s1 = 520, s2 = 460;
    const measure = (size1, size2) => {
      ctx.font = `200 ${size1}px ${NUM_FONT}`;
      const w1 = ctx.measureText(card.solid || '').width;
      ctx.font = `200 ${size2}px ${NUM_FONT}`;
      const w2 = ctx.measureText(card.outline || '').width;
      return w1 + w2 + (card.outline ? 16 : 0);
    };
    let total = measure(s1, s2);
    const maxW = 1320;
    if (total > maxW) {
      const k = maxW / total;
      s1 *= k;
      s2 *= k;
      total = measure(s1, s2);
    }
    const x0 = 320;
    let x = x0;

    label(card.label, x0 + 4, baseY - s1 * 0.95, A);

    ctx.save();
    ctx.globalAlpha = A;
    if (card.solid) {
      ctx.font = `200 ${s1}px ${NUM_FONT}`;
      ctx.fillStyle = goldFill(x, baseY, s1);
      if (D === THEMES.light) {
        ctx.shadowColor = 'rgba(120,60,20,0.20)';
        ctx.shadowBlur = 44;
        ctx.shadowOffsetY = 12;
      }
      ctx.fillText(card.solid, x, baseY);
      ctx.shadowBlur = 0;
      ctx.shadowOffsetY = 0;
      x += ctx.measureText(card.solid).width + 16;
    }
    if (card.outline) {
      ctx.font = `200 ${s2}px ${NUM_FONT}`;
      ctx.strokeStyle = D.text;
      ctx.globalAlpha = A * 0.92;
      ctx.lineWidth = 1.8;
      ctx.strokeText(card.outline, x, baseY);
    }
    ctx.restore();

    if (card.headline) {
      ctx.save();
      ctx.globalAlpha = A;
      ctx.font = `300 46px ${CN_FONT}`;
      ctx.fillStyle = D.body;
      const lines = wrap(card.headline, 1250, `300 46px ${CN_FONT}`);
      lines.forEach((ln, i) => ctx.fillText(ln, x0, baseY + 130 + i * 62));
      ctx.restore();
    }
  }

  function drawStatement(card, u, A) {
    const x0 = 320;
    if (card.kicker) label(card.kicker, x0 + 2, 360, A);
    ctx.save();
    ctx.globalAlpha = A;
    ctx.fillStyle = D.text;
    const font = `300 78px ${CN_FONT}`;
    const lines = wrap(card.headline, 1300, font);
    ctx.font = font;
    lines.forEach((ln, i) => ctx.fillText(ln, x0, 520 + i * 104));
    ctx.restore();
    if (card.note) {
      ctx.save();
      ctx.globalAlpha = A * 0.8;
      ctx.font = `300 34px ${CN_FONT}`;
      ctx.fillStyle = D.muted;
      ctx.fillText(card.note, x0 + 2, 520 + wrap(card.headline, 1300, `300 78px ${CN_FONT}`).length * 104 + 34);
      ctx.restore();
    }
  }

  function drawRule(card, u, A) {
    const x0 = 320, x1 = 1600, y = 620;
    label(card.label, x0 + 2, 400, A);
    const p = lerp(0.82, 1, easeOut(span(u, 0, 1.0)));

    if (card.segments) {
      const n = card.segments;
      const gap = 10;
      const w = (x1 - x0 - gap * (n - 1)) / n;
      for (let i = 0; i < n; i++) {
        const on = lerp(0.85, 1, easeOut(span(u, i * 0.03, 0.6 + i * 0.03)));
        if (on <= 0) continue;
        const x = x0 + i * (w + gap);
        ctx.save();
        ctx.globalAlpha = (i === 0 ? 0.95 : 0.35) * A * on;
        ctx.fillStyle = i === 0 ? D.accentHot : D.muted;
        ctx.fillRect(x, y - 8, w, 16);
        ctx.restore();
      }
      ctx.save();
      ctx.globalAlpha = 0.9 * A;
      ctx.font = `300 30px ${CN_FONT}`;
      ctx.fillStyle = D.muted;
      ctx.fillText(card.segment_label || '', x0, y - 46);
      ctx.restore();
      ctx.save();
      ctx.globalAlpha = A;
      ctx.font = `300 46px ${CN_FONT}`;
      ctx.fillStyle = D.body;
      const lines = wrap(card.headline, 1250, `300 46px ${CN_FONT}`);
      lines.forEach((ln, i) => ctx.fillText(ln, x0, y + 170 + i * 60));
      ctx.restore();
      return;
    }
    ctx.save();
    ctx.globalAlpha = 0.5 * A;
    ctx.strokeStyle = D.border;
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(x0, y);
    ctx.lineTo(lerp(x0, x1, p), y);
    ctx.stroke();
    ctx.restore();

    const cut = lerp(x0, x1, card.pct);
    ctx.save();
    ctx.globalAlpha = 0.95 * A * p;
    ctx.strokeStyle = D.accentHot;
    ctx.lineWidth = 8;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x0, y);
    ctx.lineTo(Math.min(cut, lerp(x0, x1, p)), y);
    ctx.stroke();
    ctx.fillStyle = D.accentHot;
    ctx.beginPath();
    ctx.arc(cut, y, 10, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = 0.9 * A;
    ctx.font = `300 34px ${CN_FONT}`;
    ctx.fillStyle = D.text;
    ctx.fillText(card.left, x0, y + 74);
    ctx.fillStyle = D.muted;
    ctx.textAlign = 'right';
    ctx.fillText(card.right, x1, y + 74);
    ctx.textAlign = 'left';
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = A;
    ctx.font = `300 46px ${CN_FONT}`;
    ctx.fillStyle = D.body;
    const lines = wrap(card.headline, 1250, `300 46px ${CN_FONT}`);
    lines.forEach((ln, i) => ctx.fillText(ln, x0, y + 190 + i * 60));
    ctx.restore();
  }

  function drawBars(card, u, A) {
    const n = card.n || 12;
    const x0 = 320, gap = (1280) / n, base = 780;
    const best = card.best ?? Math.floor(n / 2);
    label(card.label, x0 + 2, 360, A);
    for (let i = 0; i < n; i++) {
      const rise = lerp(0.82 + (i % 5) * 0.02, 1, easeOut(span(u, 0, 0.8)));
      const h = (80 + hash(i * 4.7) * 260) * rise;
      const x = x0 + i * gap + gap / 2;
      const chosen = i === best;
      ctx.save();
      ctx.globalAlpha = (chosen ? 0.95 : 0.42) * A;
      ctx.strokeStyle = chosen ? D.accentHot : D.muted;
      ctx.lineWidth = chosen ? 8 : 4;
      ctx.beginPath();
      ctx.moveTo(x, base);
      ctx.lineTo(x, base - h);
      ctx.stroke();
      if (chosen) {
        ctx.globalAlpha = 0.55 * A * (0.6 + 0.4 * Math.sin(u * 3.2));
        ctx.fillStyle = D.accentHot;
        ctx.beginPath();
        ctx.arc(x, base - h - 26, 7, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
    ctx.save();
    ctx.globalAlpha = A;
    ctx.font = `300 46px ${CN_FONT}`;
    ctx.fillStyle = D.body;
    ctx.fillText(card.headline, x0, 900);
    ctx.restore();
  }

  function drawFlow(card, u, A) {
    const nodes = card.nodes || [];
    const y = 620;
    const x0 = 380, x1 = 1540;
    const step = nodes.length > 1 ? (x1 - x0) / (nodes.length - 1) : 0;
    label(card.label, x0 - 60, 400, A);
    const hl = new Set(card.highlight || []);

    nodes.forEach((nd, i) => {
      const x = x0 + i * step;
      const on = lerp(0.85, 1, easeOut(span(u, i * 0.04, 0.45 + i * 0.04)));
      const chosen = hl.has(i);
      ctx.save();
      ctx.globalAlpha = A * on;
      ctx.strokeStyle = chosen ? D.accentHot : D.border;
      ctx.lineWidth = chosen ? 3.4 : 2;
      ctx.beginPath();
      ctx.arc(x, y, 74, 0, Math.PI * 2);
      ctx.stroke();
      if (chosen) {
        ctx.globalAlpha = A * on * 0.08;
        ctx.fillStyle = D.accentHot;
        ctx.fill();
        ctx.globalAlpha = A * on;
      }
      ctx.fillStyle = chosen ? D.accentHot : D.body;
      ctx.font = `300 38px ${CN_FONT}`;
      ctx.textAlign = 'center';
      ctx.fillText(nd, x, y + 13);
      ctx.textAlign = 'left';
      ctx.restore();

      if (i < nodes.length - 1) {
        const a0 = lerp(0.8, 1, easeOut(span(u, 0, 0.6)));
        ctx.save();
        ctx.globalAlpha = 0.5 * A * a0;
        ctx.strokeStyle = D.muted;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x + 84, y);
        ctx.lineTo(lerp(x + 84, x + step - 84, a0), y);
        ctx.stroke();
        ctx.restore();
      }
    });

    // when two nodes are marked, draw what the sentence means: one arc of attention
    if ((card.highlight || []).length === 2) {
      const [a, b] = card.highlight;
      const p0 = { x: x0 + a * step, y: y - 84 };
      const p1 = { x: x0 + b * step, y: y - 84 };
      const h = 90 + Math.abs(b - a) * 26;
      const c = { x: (p0.x + p1.x) / 2, y: p0.y - 2 * h };
      const grow = easeOut(span(u, 1.0, 2.2));
      if (grow > 0) {
        ctx.save();
        ctx.strokeStyle = D.accentHot;
        ctx.globalAlpha = 0.9 * A * grow;
        ctx.lineWidth = 4 + 4 * grow;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(p0.x, p0.y);
        const n = Math.max(2, Math.ceil(64 * grow));
        for (let i = 1; i <= n; i++) {
          const t2 = (i / n) * grow;
          const u2 = 1 - t2;
          ctx.lineTo(u2 * u2 * p0.x + 2 * u2 * t2 * c.x + t2 * t2 * p1.x,
                     u2 * u2 * p0.y + 2 * u2 * t2 * c.y + t2 * t2 * p1.y);
        }
        ctx.stroke();
        ctx.restore();
      }
    }

    ctx.save();
    ctx.globalAlpha = A;
    ctx.font = `300 46px ${CN_FONT}`;
    ctx.fillStyle = D.body;
    const lines = wrap(card.headline, 1250, `300 46px ${CN_FONT}`);
    lines.forEach((ln, i) => ctx.fillText(ln, 320, 880 + i * 60));
    ctx.restore();
  }

  const KINDS = { figure: drawFigure, statement: drawStatement, rule: drawRule, bars: drawBars, flow: drawFlow };

  function cardAt(t) {
    for (let i = cards.length - 1; i >= 0; i--) {
      if (t >= cards[i].t) return cards[i];
    }
    return cards[0];
  }

  function draw(t) {
    const card = cardAt(t);
    const u = Math.max(0, t - card.t);
    D = THEMES[card.theme] || THEMES.dark;

    ctx.setTransform(1, 0, 0, 1, 0, 0);
    field(t);

    const A = lerp(0.88, 1, easeOut(span(u, 0, 0.5)));
    const push = 1 + 0.04 * easeInOut(span(u, 0, card.dur));
    ctx.save();
    ctx.translate(W / 2, H / 2);
    ctx.scale(push, push);
    ctx.translate(-W / 2, -H / 2);
    ctx.textBaseline = 'alphabetic';
    (KINDS[card.kind] || drawStatement)(card, u, A);
    ctx.restore();

    overlay(t);
    const fin = 1 - easeOut(span(t, 0, 0.35));
    const fout = easeInOut(span(t, DUR - 1.6, DUR));
    const f = Math.max(fin, fout);
    if (f > 0) {
      ctx.save();
      ctx.globalAlpha = f;
      ctx.fillStyle = D.bg;
      ctx.fillRect(0, 0, W, H);
      ctx.restore();
    }
  }

  (async () => {
    const data = await (await fetch('./cards.json')).json();
    cards = data.cards;
    DUR = data.duration || cards[cards.length - 1].t + cards[cards.length - 1].dur;
    window.DUR = DUR;
    window.seek = (t) => draw(Math.max(0, Math.min(DUR, t)));
    window.seek(0);
    window.READY = true;
  })();
})();
