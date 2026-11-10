// WAYNE desktop opener — Gate 1 blockout.
// One continuous take, 12 s at 120 BPM. Pure function of t via window.seek(t).
// Variant A: geometric pip with eyes + antenna. Variant B: dot + tip.
// No materials beyond flat tokens, no shadows, no post-processing, no audio.

import * as THREE from './three.module.js';

const W = 1920, H = 1080, FPS = 30, DUR = 12;
const V = new URLSearchParams(location.search).get('variant') || 'a';

const COL = {
  paper: 0xFBFAF7, surface: 0xF3F1EA, ink: 0x252A31, body: 0x2E3338,
  muted: 0x6B7280, border: 0xE3E0D7, orange: 0xE8733B,
};

const clamp01 = v => Math.min(1, Math.max(0, v));
const smooth = v => { const x = clamp01(v); return x * x * (3 - 2 * x); };
const span = (t, a, b) => clamp01((t - a) / (b - a));

// ---------------------------------------------------------------- renderer
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(COL.paper);
const camera = new THREE.PerspectiveCamera(32, W / H, 0.05, 30);

const flat = (color, opts = {}) => new THREE.MeshStandardMaterial({
  color, roughness: 1, metalness: 0, ...opts,
});

// ---------------------------------------------------------------- light
scene.add(new THREE.HemisphereLight(0xffffff, 0xCFC8B8, 0.55));
const key = new THREE.DirectionalLight(0xffffff, 1.15);
key.position.set(-0.9, 2.1, 1.1);
scene.add(key);

// ---------------------------------------------------------------- desk
const desk = new THREE.Mesh(new THREE.PlaneGeometry(8, 6), flat(0xE7E0D2));
desk.rotation.x = -Math.PI / 2;
scene.add(desk);

{
  const pts = [];
  const step = 0.05;
  for (let x = -1.4; x <= 1.4001; x += step) pts.push(x, 0.0006, -1.0, x, 0.0006, 1.0);
  for (let z = -1.0; z <= 1.0001; z += step) pts.push(-1.4, 0.0006, z, 1.4, 0.0006, z);
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  scene.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({
    color: COL.border, transparent: true, opacity: 0.3,
  })));
}

// ---------------------------------------------------------------- cards
const CARD_Y = 0.003;
const PANEL = { x: 0, z: 0.40, w: 0.42, d: 0.26 };

// The project card and the workbench panel are the same mesh.
const panel = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), flat(COL.paper));
panel.scale.set(0.30, 0.006, 0.20);
panel.position.set(PANEL.x, CARD_Y, PANEL.z);
scene.add(panel);
const edgeMaterial = new THREE.LineBasicMaterial({ color: COL.ink, transparent: true, opacity: 0.55 });
const panelEdge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)), edgeMaterial);
panelEdge.scale.copy(panel.scale);
panelEdge.position.copy(panel.position);
scene.add(panelEdge);

const notes = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), flat(COL.paper));
notes.scale.set(0.22, 0.006, 0.14);
notes.position.set(-0.38, CARD_Y, PANEL.z + 0.04);
scene.add(notes);
const notesEdge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)), edgeMaterial);
notesEdge.scale.copy(notes.scale);
notesEdge.position.copy(notes.position);
scene.add(notesEdge);

// ---------------------------------------------------------------- chart
const CURVE = { x0: -0.17, x1: 0.17, zBase: 0.094, h: 0.135, n: 64 };
const response = u => 1 - Math.exp(-5.5 * u) * Math.cos(7.5 * u);
const curvePts = [];
for (let i = 0; i <= CURVE.n; i++) {
  const u = i / CURVE.n;
  curvePts.push(new THREE.Vector3(
    PANEL.x + CURVE.x0 + (CURVE.x1 - CURVE.x0) * u,
    0.0085,
    PANEL.z + CURVE.zBase - CURVE.h * response(u),
  ));
}
const curveGeo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(curvePts), 128, 0.0017, 6, false);
const curve = new THREE.Mesh(curveGeo, flat(COL.ink));
curve.visible = false;
scene.add(curve);
const curveIndexCount = curveGeo.index.count;

const axisMat = flat(COL.muted);
const axisX = new THREE.Mesh(new THREE.BoxGeometry(CURVE.x1 - CURVE.x0, 0.0012, 0.0012), axisMat);
axisX.position.set(PANEL.x, 0.0072, PANEL.z + CURVE.zBase);
const axisZ = new THREE.Mesh(new THREE.BoxGeometry(0.0012, 0.0012, 0.15), axisMat);
axisZ.position.set(PANEL.x + CURVE.x0, 0.0072, PANEL.z + CURVE.zBase - 0.075);
scene.add(axisX, axisZ);

const dotGeo = new THREE.SphereGeometry(0.0035, 12, 8);
const dots = [0.35, 0.55, 0.8].map(u => {
  const p = new THREE.Vector3(
    PANEL.x + CURVE.x0 + (CURVE.x1 - CURVE.x0) * u, 0.0095,
    PANEL.z + CURVE.zBase - CURVE.h * response(u),
  );
  const m = new THREE.Mesh(dotGeo, flat(COL.ink));
  m.position.copy(p); m.userData.u = u; m.visible = false;
  scene.add(m); return m;
});

const tip = new THREE.Mesh(new THREE.SphereGeometry(0.005, 16, 12), flat(COL.orange));
tip.visible = false;
scene.add(tip);

// ---------------------------------------------------------------- ripples
const rings = [0, 1].map(() => {
  const m = new THREE.Mesh(
    new THREE.RingGeometry(0.004, 0.006, 40),
    new THREE.MeshBasicMaterial({ color: COL.orange, transparent: true, opacity: 0, side: THREE.DoubleSide }),
  );
  m.rotation.x = -Math.PI / 2;
  m.visible = false;
  scene.add(m); return m;
});

// ---------------------------------------------------------------- brand mark
// W_PATH and CURRENT_PATH copied verbatim from RemotionStudio/src/brand/BrandMark.tsx.
const W_PATH = [[24, 44], [66, 132], [120, 68], [174, 132], [216, 44]];
const CURRENT_PATH = [[75, 121], [113, 77]];
const K = 0.60 / 192;               // 192 path units -> 0.60 m
const W_Z = -0.16;                  // mark sits above the workbench in the final frame
const mapW = ([sx, sy]) => new THREE.Vector3((sx - 120) * K, 0.0, (sy - 88) * K + W_Z);

function ribbon(p0, p1, color, width = 0.040, thick = 0.0025, y = 0.0026) {
  const dx = p1.x - p0.x, dz = p1.z - p0.z;
  const len = Math.hypot(dx, dz);
  const g = new THREE.Group();
  g.position.set(p0.x, y, p0.z);
  g.rotation.y = Math.atan2(dx, dz);
  const body = new THREE.Mesh(new THREE.BoxGeometry(width, thick, len), flat(color));
  body.position.z = len / 2;
  g.add(body);
  g.scale.z = 0.0001;
  g.visible = false;
  scene.add(g);
  return g;
}
const wSegs = [];
for (let i = 0; i < W_PATH.length - 1; i++) {
  wSegs.push(ribbon(mapW(W_PATH[i]), mapW(W_PATH[i + 1]), COL.ink));
}
const wCurrent = ribbon(mapW(CURRENT_PATH[0]), mapW(CURRENT_PATH[1]), COL.orange, 0.013, 0.0038, 0.0034);

// ---------------------------------------------------------------- pointers
function makePip() {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.BoxGeometry(0.058, 0.044, 0.048), flat(COL.paper));
  body.position.y = 0.025; g.add(body);
  const bodyEdge = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(0.058, 0.044, 0.048)), edgeMaterial);
  bodyEdge.position.y = 0.025; g.add(bodyEdge);
  const eyeGeo = new THREE.SphereGeometry(0.0042, 14, 10);
  const eyeL = new THREE.Mesh(eyeGeo, flat(COL.ink));
  eyeL.position.set(-0.0065, 0.029, 0.0275);
  const eyeR = eyeL.clone(); eyeR.position.x = 0.0065;
  g.add(eyeL, eyeR);
  const stem = new THREE.Mesh(new THREE.CylinderGeometry(0.0013, 0.0013, 0.016, 8), flat(COL.ink));
  stem.position.set(0, 0.055, 0); g.add(stem);
  const antTip = new THREE.Mesh(new THREE.SphereGeometry(0.0042, 14, 10), flat(COL.orange));
  antTip.position.set(0, 0.064, 0); g.add(antTip);
  const armGeo = new THREE.CylinderGeometry(0.0030, 0.0030, 0.020, 8);
  const armL = new THREE.Mesh(armGeo, flat(COL.ink));
  armL.position.set(-0.031, 0.016, 0.010); armL.rotation.x = 0.9;
  const armR = armL.clone(); armR.position.x = 0.031;
  g.add(armL, armR);
  g.userData = { body, eyeL, eyeR, antTip, armL, armR };
  scene.add(g);
  return g;
}

function makeDot() {
  const g = new THREE.Group();
  const dot = new THREE.Mesh(new THREE.SphereGeometry(0.010, 20, 14), flat(COL.ink));
  dot.position.y = 0.011; g.add(dot);
  const t = new THREE.Mesh(new THREE.SphereGeometry(0.004, 12, 8), flat(COL.orange));
  t.position.set(0, 0.011, 0.0095); g.add(t);
  g.userData = { body: dot, antTip: t };
  scene.add(g);
  return g;
}

const pointer = V === 'b' ? makeDot() : makePip();
const MAT_ORANGE = flat(COL.orange), MAT_INK = flat(COL.ink);

// Path of the pointer on the desk. y is height above the desk.
function pointerState(t) {
  const pz = PANEL.z;
  if (V === 'b') {
    if (t < 0.50) return { x: 1.15, y: 0.02, z: pz + 0.04, s: 1 };
    if (t < 0.85) {
      const p = smooth(span(t, 0.50, 0.85));
      return { x: 1.15 + (0.38 - 1.15) * p, y: 0.012 + 0.05 * Math.sin(Math.PI * p), z: pz + 0.04 + (pz + 0.16 - pz - 0.04) * p, s: 1 };
    }
    if (t < 2.0) return { x: 0.38, y: 0.012, z: pz + 0.16, s: 1 };
    if (t < 3.3) {
      const p = smooth(span(t, 2.0, 3.3));
      return { x: 0.38 + (0.22 - 0.38) * p, y: 0.012 + 0.02 * Math.sin(Math.PI * p), z: pz + 0.16 + (pz + 0.02 - pz - 0.16) * p, s: 1 };
    }
    if (t < 4.5) return { x: 0.22, y: 0.012, z: pz + 0.02, s: t > 3.44 && t < 3.62 ? 0.9 : 1 };
    if (t < 4.9) {
      const p = smooth(span(t, 4.5, 4.9));
      return { x: 0.22 + (-0.30 - 0.22) * p, y: 0.012, z: pz + 0.02 + (pz + 0.20 - pz - 0.02) * p, s: 1 };
    }
    if (t < 9.0) return { x: -0.30, y: 0.012, z: pz + 0.20, s: 1 };
    if (t < 10.30) {
      const p = smooth(span(t, 9.0, 10.30));
      const start = mapW(W_PATH[0]);
      return {
        x: -0.30 + (start.x - -0.30) * p, y: 0.012 + (0.006 - 0.012) * p,
        z: pz + 0.20 + (start.z - pz - 0.20) * p, s: 1 - 0.97 * smooth(span(t, 10.0, 10.3)),
      };
    }
    { const st = mapW(W_PATH[0]); return { x: st.x, y: 0.006, z: st.z, s: 0.001 }; }
  }
  // A: one hop in, one short glide, then a retreat
  if (t < 0.50) return { x: 1.15, y: 0.02, z: pz + 0.06, s: 1 };
  if (t < 0.85) {
    const p = span(t, 0.50, 0.85);
    return { x: 1.15 + (0.38 - 1.15) * smooth(p), y: 0.012 + 0.10 * Math.sin(Math.PI * p), z: pz + 0.06 + (pz + 0.16 - pz - 0.06) * smooth(p), s: 1 + 0.08 * Math.sin(Math.PI * p) };
  }
  if (t < 2.0) return { x: 0.38, y: 0.012, z: pz + 0.16, s: 1 };
  if (t < 3.3) {
    const p = smooth(span(t, 2.0, 3.3));
    return { x: 0.38 + (0.22 - 0.38) * p, y: 0.012 + 0.025 * Math.sin(Math.PI * p), z: pz + 0.16 + (pz + 0.02 - pz - 0.16) * p, s: 1 };
  }
  if (t < 4.6) return { x: 0.22, y: 0.012, z: pz + 0.02, s: t > 3.44 && t < 3.62 ? 0.92 : 1 };
  if (t < 5.0) {
    const p = smooth(span(t, 4.6, 5.0));
    return { x: 0.22 + (-0.30 - 0.22) * p, y: 0.012, z: pz + 0.02 + (pz + 0.20 - pz - 0.02) * p, s: 1 };
  }
  if (t < 9.0) return { x: -0.30, y: 0.012, z: pz + 0.20, s: 1 };
  if (t < 10.4) {
    const p = smooth(span(t, 9.0, 10.4));
    return { x: -0.30 + (0.62 - -0.30) * p, y: 0.012 + 0.03 * Math.sin(Math.PI * p), z: pz + 0.20 + (0.70 - pz - 0.20) * p, s: 1 };
  }
  return { x: 0.62, y: 0.012, z: 0.62, s: 1 };
}

// ---------------------------------------------------------------- camera
const CAM = [
  { t: 0.0, p: [0.58, 0.66, 0.98], l: [0.00, 0.00, 0.22] },
  { t: 0.5, p: [0.58, 0.66, 0.98], l: [0.00, 0.00, 0.22] },
  { t: 2.0, p: [0.64, 0.66, 0.96], l: [0.00, 0.00, 0.30] },
  { t: 7.0, p: [0.60, 0.62, 0.92], l: [0.01, 0.00, 0.34] },
  { t: 9.0, p: [0.52, 0.58, 0.84], l: [0.02, 0.00, 0.28] },
  { t: 11.0, p: [0.16, 1.16, 0.82], l: [0.00, 0.00, 0.02] },
  { t: 11.5, p: [0.10, 1.20, 0.75], l: [0.00, 0.00, 0.02] },
  { t: 12.0, p: [0.10, 1.20, 0.75], l: [0.00, 0.00, 0.02] },
];
const tmpA = new THREE.Vector3(), tmpB = new THREE.Vector3();
function cameraAt(t) {
  let i = 0;
  while (i < CAM.length - 2 && t > CAM[i + 1].t) i++;
  const a = CAM[i], b = CAM[i + 1];
  const u = smooth(span(t, a.t, b.t));
  tmpA.fromArray(a.p); tmpB.fromArray(b.p);
  camera.position.copy(tmpA).lerp(tmpB, u);
  tmpA.fromArray(a.l); tmpB.fromArray(b.l);
  camera.lookAt(tmpA.lerp(tmpB, u));
}

// ---------------------------------------------------------------- overlay
const $ = id => document.getElementById(id);
const els = {
  project: $('label-project'), notes: $('label-notes'), term: $('term'),
  typed: $('typed'), caret: $('caret'), wordmark: $('wordmark'), tagline: $('tagline'),
};
const project3 = new THREE.Vector3(PANEL.x, 0.01, PANEL.z);
const notes3 = new THREE.Vector3(-0.38, 0.01, PANEL.z + 0.04);
const term3 = new THREE.Vector3(PANEL.x - 0.19, 0.012, PANEL.z - 0.10);
const wm3 = new THREE.Vector3(0, 0.002, 0.10);
const tag3 = new THREE.Vector3(0, 0.002, 0.17);
const v3 = new THREE.Vector3();

function screenOf(p) {
  v3.copy(p).project(camera);
  return { x: (v3.x * 0.5 + 0.5) * W, y: (-v3.y * 0.5 + 0.5) * H, z: v3.z };
}
function ppmAt(p) {
  const a = screenOf(p);
  const b = screenOf(v3.copy(p).add(new THREE.Vector3(0.1, 0, 0)));
  return Math.hypot(b.x - a.x, b.y - a.y) / 0.1;
}

function place(el, p, worldHeight, centered, visible) {
  if (!visible) { el.style.display = 'none'; return; }
  const s = screenOf(p);
  const px = Math.max(8, ppmAt(p) * worldHeight);
  el.style.display = 'block';
  el.style.fontSize = `${px.toFixed(2)}px`;
  el.style.transform = centered
    ? `translate(${s.x.toFixed(2)}px, ${s.y.toFixed(2)}px) translate(-50%, -50%)`
    : `translate(${s.x.toFixed(2)}px, ${s.y.toFixed(2)}px) translate(0, -50%)`;
}

// ---------------------------------------------------------------- world update
const typedFull = '$ render lesson';

function update(t) {
  cameraAt(t);

  // cards
  const cardIn = smooth(span(t, 1.0, 1.55));
  panel.position.x = PANEL.x - 1.10 * (1 - cardIn);
  panel.rotation.z = 0.10 * (1 - cardIn);
  const unfold = smooth(span(t, 4.0, 4.45));
  const lift = t > 3.5 && t < 3.72 ? 0.002 * Math.sin(Math.PI * span(t, 3.5, 3.72)) : 0;
  panel.position.y = CARD_Y + lift;
  panel.scale.set(
    0.30 + (PANEL.w - 0.30) * unfold,
    0.006,
    0.20 + (PANEL.d - 0.20) * unfold,
  );
  panelEdge.scale.copy(panel.scale);
  panelEdge.position.copy(panel.position);
  panel.visible = panelEdge.visible = t >= 1.0;

  const drop = span(t, 1.5, 1.8);
  notes.position.y = CARD_Y + 0.30 * (1 - smooth(drop)) * (1 - 0.06 * Math.sin(Math.PI * drop));
  notes.visible = notesEdge.visible = t >= 1.5;
  const leave = smooth(span(t, 9.0, 9.7));
  notes.position.z = PANEL.z + 0.04 + 1.30 * leave;
  notes.rotation.y = 0.12 * (1 - smooth(drop));
  notesEdge.position.copy(notes.position);
  notesEdge.position.z = notes.position.z;
  notesEdge.rotation.copy(notes.rotation);

  // chart
  const grow = smooth(span(t, 7.0, 8.0));
  curve.visible = t >= 7.0;
  curveGeo.setDrawRange(0, Math.max(0, Math.floor(curveIndexCount * grow)));
  axisX.visible = axisZ.visible = t >= 4.0;
  dots.forEach(d => { d.visible = t >= 7.0 && grow > d.userData.u; });
  const tipIdx = Math.min(curvePts.length - 1, Math.floor(grow * CURVE.n));
  tip.position.copy(curvePts[tipIdx]);
  tip.visible = t >= 7.0 && t < 9.0;
  if (tip.visible) {
    const k = 1 + 0.15 * Math.sin(Math.PI * span(t, 7.95, 8.20));
    tip.scale.setScalar(k);
  }

  // ripples
  const r1 = span(t, 3.50, 3.80);
  const r2 = span(t, 7.00, 7.30);
  [[rings[0], r1, new THREE.Vector3(0.20, 0.006, PANEL.z + 0.02)],
   [rings[1], r2, new THREE.Vector3(PANEL.x - 0.12, 0.006, PANEL.z - 0.04)]].forEach(([m, p, at]) => {
    m.visible = p > 0 && p < 1;
    if (m.visible) {
      m.position.copy(at);
      m.scale.setScalar(1 + 2.2 * p);
      m.material.opacity = 0.9 * (1 - p);
    }
  });

  // pointer
  const ps = pointerState(t);
  pointer.position.set(ps.x, ps.y, ps.z);
  pointer.scale.setScalar(ps.s);
  if (V === 'a') {
    const u = pointer.userData;
    const breathe = 1 + 0.005 * Math.sin((Math.PI * 2 * t) / 2.4);
    u.body.scale.set(1, breathe, 1);
    const blink = (t % 2.4) < 0.12 ? 0.12 : 1;
    u.eyeL.scale.y = u.eyeR.scale.y = blink;
    const extending = t > 3.40 && t < 3.68 ? Math.sin(Math.PI * span(t, 3.40, 3.68)) : 0;
    u.armL.rotation.x = 0.9 - 1.3 * extending;
    u.armR.rotation.x = 0.9 - 1.3 * extending;
    u.antTip.material = t < 3.5 ? MAT_ORANGE : MAT_INK;
    const mix = smooth(span(t, 3.2, 3.5));
    const tx = 0.20 + (PANEL.x - 0.20) * mix;
    const tz = (PANEL.z + 0.02) + ((PANEL.z - 0.02) - (PANEL.z + 0.02)) * mix;
    const camYaw = Math.atan2(camera.position.x - ps.x, camera.position.z - ps.z);
    const tgtYaw = Math.atan2(tx - ps.x, tz - ps.z);
    let d = tgtYaw - camYaw;
    while (d > Math.PI) d -= Math.PI * 2;
    while (d < -Math.PI) d += Math.PI * 2;
    pointer.rotation.y = camYaw + 0.55 * d;
  } else {
    const u = pointer.userData;
    u.antTip.material = t < 3.5 ? MAT_ORANGE : MAT_INK;
  }

  // W
  const wIn = t - 10.0;
  const win = [[0.00, 0.28], [0.22, 0.50], [0.44, 0.72], [0.66, 0.95]];
  wSegs.forEach((seg, i) => {
    seg.visible = t >= 10.0;
    seg.scale.z = Math.max(0.0001, span(wIn, win[i][0], win[i][1]));
  });
  wCurrent.visible = t >= 11.5;
  wCurrent.scale.z = Math.max(0.0001, span(t, 11.5, 11.75));

  // overlay
  place(els.project, project3, 0.030, true, t >= 1.0 && t < 4.0);
  place(els.notes, notes3, 0.020, true, t >= 1.5 && t < 5.0);
  const typed = Math.floor(clamp01((t - 5.0) / 1.5) * typedFull.length);
  els.typed.textContent = typedFull.slice(0, typed);
  els.typed.className = t >= 7.0 ? 'dim' : '';
  els.caret.style.color = t >= 4.0 && t < 7.0 ? '#E8733B' : '#6B7280';
  els.caret.style.display = t >= 4.6 && t < 7.0 ? 'inline' : 'none';
  place(els.term, term3, 0.020, false, t >= 4.45);
  place(els.wordmark, wm3, 0.085, true, t >= 11.0);
  place(els.tagline, tag3, 0.033, true, t >= 11.0);

  renderer.render(scene, camera);
}

window.DUR = DUR;
window.seek = t => { update(t); };

document.fonts.ready.then(() => {
  update(0);
  window.READY = true;
});
