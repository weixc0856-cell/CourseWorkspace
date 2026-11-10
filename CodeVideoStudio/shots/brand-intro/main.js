// WAYNE — desktop opener (v2, Blender character).
// The figure is modelled in Blender (build_character.py -> character.json) and
// animated here; scene, camera, post and pacing keep the v1 language.
// The finished sheet lifts off the desk and stands facing the camera, so the
// mark is seen straight on. Pure function of t via window.seek(t).

import * as THREE from 'three';
import { EffectComposer } from './vendor/three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/three/addons/postprocessing/RenderPass.js';
import { BokehPass } from './vendor/three/addons/postprocessing/BokehPass.js';
import { UnrealBloomPass } from './vendor/three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from './vendor/three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from './vendor/three/addons/postprocessing/OutputPass.js';
import { VignetteShader } from './vendor/three/addons/shaders/VignetteShader.js';
import { FXAAShader } from './vendor/three/addons/shaders/FXAAShader.js';

const W = 1920, H = 1080, DUR = 20;
const COL = {
  paper: 0xFBFAF7, surface: 0xF3F1EA, ink: 0x252A31, muted: 0x6B7280,
  border: 0xE3E0D7, orange: 0xE8733B,
};

const clamp01 = v => Math.min(1, Math.max(0, v));
const smooth = v => { const x = clamp01(v); return x * x * (3 - 2 * x); };
const span = (t, a, b) => clamp01((t - a) / (b - a));
const lerp = (a, b, u) => a + (b - a) * u;

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------- renderer
const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(COL.paper);
const camera = new THREE.PerspectiveCamera(34, W / H, 0.03, 60);

// ---------------------------------------------------------------- textures
function canvasTex(size, draw, repeat = 1) {
  const c = document.createElement('canvas');
  c.width = c.height = size;
  draw(c.getContext('2d'), size);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(repeat, repeat);
  t.anisotropy = 4;
  return t;
}

const paperTex = canvasTex(512, (g, s) => {
  const rnd = mulberry32(7);
  g.fillStyle = '#FBFAF7';
  g.fillRect(0, 0, s, s);
  for (let i = 0; i < 20000; i++) {
    const v = 246 + Math.floor(rnd() * 8);
    g.fillStyle = `rgba(${v},${v - 2},${v - 6},0.45)`;
    g.fillRect(rnd() * s, rnd() * s, 1, 1);
  }
  g.strokeStyle = 'rgba(227,224,215,0.22)';
  g.lineWidth = 1;
  for (let i = 0; i < 14; i++) {
    const y = rnd() * s;
    g.beginPath(); g.moveTo(0, y); g.lineTo(s, y + (rnd() - 0.5) * 3); g.stroke();
  }
}, 5);

const gridTex = canvasTex(1024, (g, s) => {
  g.clearRect(0, 0, s, s);
  g.strokeStyle = 'rgba(227,224,215,0.55)';
  g.lineWidth = 2;
  const step = s / 20;
  for (let i = 0; i <= 20; i++) {
    g.globalAlpha = 0.5 - Math.abs(i - 10) * 0.025;
    g.beginPath(); g.moveTo(i * step, 0); g.lineTo(i * step, s); g.stroke();
    g.beginPath(); g.moveTo(0, i * step); g.lineTo(s, i * step); g.stroke();
  }
  g.globalAlpha = 1;
}, 3);

const blobTex = canvasTex(256, (g, s) => {
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0, 'rgba(60,55,45,0.5)');
  grd.addColorStop(0.6, 'rgba(60,55,45,0.16)');
  grd.addColorStop(1, 'rgba(60,55,45,0)');
  g.fillStyle = grd; g.fillRect(0, 0, s, s);
});

// ---------------------------------------------------------------- materials
const paperMat = new THREE.MeshPhysicalMaterial({
  map: paperTex, color: 0xffffff, roughness: 0.8, metalness: 0,
  sheen: 0.3, sheenRoughness: 0.7, sheenColor: new THREE.Color(0xffffff),
});
const inkMat = new THREE.MeshStandardMaterial({ color: COL.ink, roughness: 0.55 });
const mutedMat = new THREE.MeshStandardMaterial({ color: COL.muted, roughness: 0.8 });
const ceramicMat = new THREE.MeshPhysicalMaterial({
  color: COL.paper, roughness: 0.48, metalness: 0,
  clearcoat: 0.06, clearcoatRoughness: 0.6,
});
const orangeMat = new THREE.MeshStandardMaterial({
  color: COL.orange, roughness: 0.4, emissive: COL.orange, emissiveIntensity: 0.35,
});
const warmgrayMat = new THREE.MeshStandardMaterial({ color: 0xC9C2B4, roughness: 0.6 });
const graphiteMat = new THREE.MeshStandardMaterial({ color: 0x2A2E33, roughness: 0.45, metalness: 0.35 });
const copperMat = new THREE.MeshStandardMaterial({ color: 0xC97B4E, roughness: 0.3, metalness: 0.85 });
const visorMat = new THREE.MeshPhysicalMaterial({ color: 0x0B0E12, roughness: 0.14, metalness: 0.1, clearcoat: 1 });
const eyeMat = new THREE.MeshStandardMaterial({
  color: 0xFF6A2A, emissive: 0xFF5A1E, emissiveIntensity: 1.4, roughness: 0.3,
});

// ---------------------------------------------------------------- light
scene.add(new THREE.HemisphereLight(0xffffff, 0xD9D2C2, 0.42));
const key = new THREE.DirectionalLight(0xfff6ea, 2.2);
key.position.set(-1.4, 2.6, 1.7);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -1.6; key.shadow.camera.right = 1.6;
key.shadow.camera.top = 1.6; key.shadow.camera.bottom = -1.6;
key.shadow.camera.near = 0.1; key.shadow.camera.far = 8;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.015;
key.shadow.radius = 4;
scene.add(key);
const rim = new THREE.DirectionalLight(0xffffff, 0.9);
rim.position.set(0.9, 1.6, -1.4);
scene.add(rim);
const cardFill = new THREE.DirectionalLight(0xffffff, 0.0);
cardFill.position.set(0.2, 0.9, 1.6);
scene.add(cardFill);

// ---------------------------------------------------------------- desk
const desk = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({
  map: paperTex, color: 0xEDE6D8, roughness: 0.95, metalness: 0,
}));
desk.rotation.x = -Math.PI / 2;
desk.receiveShadow = true;
scene.add(desk);

const grid = new THREE.Mesh(new THREE.PlaneGeometry(2.8, 2.2), new THREE.MeshBasicMaterial({
  map: gridTex, transparent: true, opacity: 0.45, depthWrite: false,
}));
grid.rotation.x = -Math.PI / 2;
grid.position.y = 0.0004;
scene.add(grid);

// ---------------------------------------------------------------- cards & props
const PANEL = { z: 0.42, w: 0.42, d: 0.28 };
const card = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), paperMat);
card.scale.set(0.26, 0.004, 0.18);
card.position.set(0, 0.002, PANEL.z);
card.castShadow = card.receiveShadow = true;
scene.add(card);

const cardEdge = new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1)),
  new THREE.LineBasicMaterial({ color: COL.ink, transparent: true, opacity: 0.3 }),
);
cardEdge.scale.copy(card.scale);
cardEdge.position.copy(card.position);
scene.add(cardEdge);

const sheet = new THREE.Mesh(new THREE.BoxGeometry(0.20, 0.003, 0.14), paperMat);
sheet.position.set(-0.52, 0.0015, 0.60);
sheet.rotation.y = 0.28;
sheet.castShadow = sheet.receiveShadow = true;
scene.add(sheet);

[0, 1, 2].forEach(i => {
  const m = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.0016, 0.17), paperMat);
  m.position.set(-0.55 + i * 0.004, 0.001 + i * 0.0017, 0.30 - i * 0.003);
  m.rotation.y = 0.42 + i * 0.03;
  m.castShadow = m.receiveShadow = true;
  scene.add(m);
});

const ruler = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.0018, 0.026), paperMat);
ruler.position.set(0.62, 0.001, 0.52);
ruler.rotation.y = -0.35;
ruler.castShadow = ruler.receiveShadow = true;
scene.add(ruler);

// ---------------------------------------------------------------- chart
const CH = { x0: -0.17, x1: 0.17, zBase: 0.09, h: 0.13, n: 64 };
const response = u => 1 - Math.exp(-5.5 * u) * Math.cos(7.5 * u);
const chartPts = u => new THREE.Vector3(
  CH.x0 + (CH.x1 - CH.x0) * u, 0.0070, CH.zBase - CH.h * response(u),
);
const pts = [];
for (let i = 0; i <= CH.n; i++) pts.push(chartPts(i / CH.n));
const curveGeo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 160, 0.0016, 8, false);
const curve = new THREE.Mesh(curveGeo, inkMat);
curve.visible = false;
scene.add(curve);
const curveCount = curveGeo.index.count;

const axisMat = new THREE.MeshStandardMaterial({ color: COL.muted, roughness: 0.9 });
const axisX = new THREE.Mesh(new THREE.BoxGeometry(CH.x1 - CH.x0, 0.0011, 0.0011), axisMat);
const axisZ = new THREE.Mesh(new THREE.BoxGeometry(0.0011, 0.0011, 0.145), axisMat);
scene.add(axisX, axisZ);

const dotGeo = new THREE.SphereGeometry(0.0032, 12, 8);
const dots = [0.35, 0.55, 0.8].map(u => {
  const m = new THREE.Mesh(dotGeo, inkMat);
  m.userData.u = u; m.visible = false;
  scene.add(m); return m;
});
const tip = new THREE.Mesh(new THREE.SphereGeometry(0.0052, 16, 12), orangeMat);
tip.visible = false;
scene.add(tip);

// ---------------------------------------------------------------- ripples
const rings = [0, 1, 2].map(() => {
  const m = new THREE.Mesh(
    new THREE.RingGeometry(0.004, 0.0065, 48),
    new THREE.MeshBasicMaterial({ color: COL.orange, transparent: true, opacity: 0, side: THREE.DoubleSide }),
  );
  m.rotation.x = -Math.PI / 2;
  m.visible = false;
  scene.add(m); return m;
});

// ---------------------------------------------------------------- character
const data = await fetch('./character.json').then(r => r.json());
const hero = new THREE.Group();
hero.scale.setScalar(0.55);
scene.add(hero);

const vc = m => { const c = m.clone(); c.vertexColors = true; return c; };
const matMap = {
  ceramic: vc(ceramicMat), warmgray: vc(warmgrayMat), graphite: vc(graphiteMat),
  copper: vc(copperMat), visor: vc(visorMat), eye: vc(eyeMat), orange: vc(orangeMat),
};
const groups = {};
for (const g of data.groups) {
  groups[g.name] = { grp: new THREE.Group(), pivot: new THREE.Vector3(...g.pivot) };
}
for (const g of data.groups) {
  const parent = g.parent === 'Root' ? hero : groups[g.parent].grp;
  const pp = g.parent === 'Root' ? new THREE.Vector3() : groups[g.parent].pivot;
  parent.add(groups[g.name].grp);
  groups[g.name].grp.position.copy(groups[g.name].pivot).sub(pp);
}
const nodes = {};
for (const p of data.parts) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(p.positions, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(p.normals, 3));
  geo.setIndex(p.indices);
  if (p.colors) geo.setAttribute('color', new THREE.Float32BufferAttribute(p.colors, 3));
  const mesh = new THREE.Mesh(geo, matMap[p.mat] || matMap.ceramic);
  mesh.castShadow = mesh.receiveShadow = true;
  const grp = groups[p.group];
  mesh.position.copy(new THREE.Vector3(...p.pivot)).sub(grp.pivot);
  grp.grp.add(mesh);
  nodes[p.name] = mesh;
}
const bodyG = groups.Body.grp, headG = groups.Head.grp;
const shL = groups.ShoulderL.grp, shR = groups.ShoulderR.grp;
const elL = groups.ElbowL.grp, elR = groups.ElbowR.grp;
const hipL = groups.HipL.grp, hipR = groups.HipR.grp;
const kneeL = groups.KneeL.grp, kneeR = groups.KneeR.grp;
const eyeL = nodes.EyeL, eyeR = nodes.EyeR, tipNode = nodes.AntennaTip;

const blob = new THREE.Mesh(new THREE.PlaneGeometry(0.46, 0.46), new THREE.MeshBasicMaterial({
  map: blobTex, transparent: true, depthWrite: false, opacity: 0.5,
}));
blob.rotation.x = -Math.PI / 2;
blob.position.y = 0.0007;
scene.add(blob);

// ---------------------------------------------------------------- character motion
function charState(t) {
  let x = 1.35, z = 0.36, y = 0, yaw = -1.4, lean = 0;
  let swingR = 0, swingL = 0, stepL = 0, stepR = 0, visor = 1;

  if (t < 0.50) return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR, visor };

  if (t < 1.05) {                                   // entry hop
    const p = smooth(span(t, 0.50, 1.05));
    x = lerp(1.35, 0.46, p); z = lerp(0.36, 0.34, p);
    y = 0.143 * Math.sin(Math.PI * p);
    yaw = lerp(-1.4, -0.6, p);
    stepL = stepR = 0.5 * Math.sin(Math.PI * p);
    swingL = swingR = -0.35 * Math.sin(Math.PI * p);
    lean = 0.08 * Math.sin(Math.PI * p);
    return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR, visor: 0.85 };
  }

  x = 0.46; z = 0.34;
  const faceYaw = (tx, tz) => Math.atan2(tx - x, tz - z);

  if (t < 2.0) {
    yaw = lerp(-0.6, faceYaw(0, PANEL.z), smooth(span(t, 1.05, 1.6)));
  } else if (t < 3.0) {                             // look around
    yaw = faceYaw(0, PANEL.z) + 0.45 * Math.sin(Math.PI * 2 * (t - 2.0) / 2.0);
    visor = 0.9;
  } else if (t < 3.5) {                             // spot it
    yaw = faceYaw(0, PANEL.z) + 0.45 * Math.sin(Math.PI * 2 * (t - 2.0) / 2.0) * (1 - smooth(span(t, 3.0, 3.25)));
    visor = 0.9 + 0.1 * smooth(span(t, 3.0, 3.3));
  } else if (t < 4.20) {                            // hop to the card
    const p = smooth(span(t, 3.5, 4.2));
    x = lerp(0.46, -0.26, p); z = lerp(0.34, 0.235, p);
    y = 0.088 * Math.sin(Math.PI * p);
    yaw = faceYaw(0.0, PANEL.z - 0.1);
    stepL = stepR = 0.45 * Math.sin(Math.PI * p);
    swingL = swingR = -0.3 * Math.sin(Math.PI * p);
    lean = 0.06 * Math.sin(Math.PI * p);
  } else if (t < 5.0) {                             // lean in
    x = -0.26; z = 0.235;
    yaw = faceYaw(0.0, PANEL.z);
    lean = 0.10 * smooth(span(t, 4.2, 4.9));
    swingR = -0.25 * smooth(span(t, 4.3, 4.9));
    visor = 1;
  } else if (t < 5.35) {                            // tap
    x = -0.26; z = 0.235; lean = 0.10; yaw = faceYaw(0.0, PANEL.z); visor = 1;
    const p = Math.sin(Math.PI * span(t, 5.0, 5.22));
    swingR = -1.25 * p;
    lean += 0.06 * p;
  } else if (t < 5.95) {                            // step back
    const p = smooth(span(t, 5.35, 5.9));
    x = lerp(-0.26, -0.38, p); z = lerp(0.235, 0.235, p);
    y = 0.017 * Math.sin(Math.PI * span(t, 5.35, 5.8));
    yaw = faceYaw(0.0, PANEL.z);
    lean = 0.10 * (1 - p);
    stepL = 0.25 * p; stepR = -0.25 * p;
  } else if (t < 8.4) {                             // typing
    x = -0.38; z = 0.235; yaw = faceYaw(0.0, PANEL.z); visor = 0.92;
    lean = 0.05;
    const beat = (t - 6.0) / 0.5;
    const k = 1 - Math.abs((beat % 1) * 2 - 1);
    swingR = -0.18 - 0.12 * k;
    swingL = 0.05 * k;
  } else if (t < 8.8) {                             // enter
    x = -0.38; z = 0.235; yaw = faceYaw(0.0, PANEL.z); visor = 1;
    const p = Math.sin(Math.PI * span(t, 8.5, 8.74));
    swingR = -0.9 * p; lean = 0.05 + 0.06 * p;
  } else if (t < 12.3) {                            // watch the result
    x = -0.38; z = 0.235; yaw = faceYaw(0.0, PANEL.z); visor = 1;
    lean = -0.07 * smooth(span(t, 9.0, 11.0));
  } else if (t < 15.0) {                            // drag the panel
    const p = smooth(span(t, 12.3, 14.1));
    const panelX = lerp(0, -0.28, p);
    x = panelX + 0.27; z = 0.235;
    yaw = faceYaw(panelX + 0.1, PANEL.z);
    lean = -0.14 * smooth(span(t, 12.3, 12.7)) * (1 - 0.6 * smooth(span(t, 14.0, 14.6)));
    swingR = -0.8 * smooth(span(t, 12.2, 12.6)) * (1 - smooth(span(t, 14.0, 14.4)));
    stepL = 0.18 * Math.sin(Math.PI * 2 * (t - 12.3) / 0.55);
    stepR = -stepL;
  } else if (t < 16.6) {                            // steps aside, leaving the sheet alone
    const p = smooth(span(t, 15.0, 16.5));
    x = lerp(0.02, -1.15, p);
    z = lerp(0.22, 0.28, p);
    y = 0.039 * Math.sin(Math.PI * span(t, 15.2, 15.8));
    yaw = -1.2;
    lean = -0.04 * p;
    stepL = 0.3 * Math.sin(Math.PI * 2 * (t - 15.0) / 0.5);
    stepR = -stepL;
    swingL = swingR = 0.12;
  } else {                                          // out of frame
    x = -1.15; z = 0.28; yaw = -1.2;
    visor = 1;
    swingL = swingR = 0.12;
  }

  return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR, visor };
}

const landing = [1.05, 4.20, 5.90, 15.8];

function poseChar(t) {
  const s = charState(t);
  hero.position.set(s.x, s.y, s.z);
  hero.rotation.y = s.yaw;
  bodyG.rotation.x = s.lean;
  headG.rotation.x = -0.3 * s.lean;

  let sq = 0;
  for (const tl of landing) {
    const d = t - tl;
    if (d >= 0 && d < 0.22) sq = Math.max(sq, 0.11 * Math.sin(Math.PI * d / 0.22));
  }
  const breath = 1 + 0.004 * Math.sin((Math.PI * 2 * t) / 2.4);
  bodyG.scale.set(1 + 0.05 * sq, (1 - sq) * breath, 1 + 0.05 * sq);

  shL.rotation.x = s.swingL;
  shR.rotation.x = s.swingR;
  elL.rotation.x = -0.35 * s.swingL;
  elR.rotation.x = -0.35 * s.swingR;
  hipL.rotation.x = s.stepL;
  hipR.rotation.x = s.stepR;
  kneeL.rotation.x = -0.45 * s.stepL;
  kneeR.rotation.x = -0.45 * s.stepR;

  const blink = (t % 3.2) < 0.12 ? 0.15 : 1;
  eyeL.scale.y = eyeR.scale.y = blink;
  matMap.eye.emissiveIntensity = 1.1 + 0.5 * s.visor;

  tipNode.material.emissiveIntensity = 0.30 + 0.15 * (0.5 + 0.5 * Math.cos(Math.PI * 2 * (t / 0.5)));

  blob.position.set(s.x, 0.0007, s.z);
  blob.material.opacity = 0.5 * clamp01(1 - s.y * 2.2);
  blob.scale.setScalar(0.6 * (1 + s.y * 1.4));
  return s;
}

// ---------------------------------------------------------------- brand card
const brandCard = new THREE.Group();
scene.add(brandCard);
brandCard.visible = false;

brandCard.add(new THREE.Mesh(new THREE.PlaneGeometry(0.96, 0.56), paperMat));
brandCard.add(new THREE.LineSegments(
  new THREE.EdgesGeometry(new THREE.PlaneGeometry(0.96, 0.56)),
  new THREE.LineBasicMaterial({ color: COL.border }),
));

// W_PATH / CURRENT_PATH copied verbatim from RemotionStudio/src/brand/BrandMark.tsx.
const W_PATH = [[24, 44], [66, 132], [120, 68], [174, 132], [216, 44]];
const CURRENT_PATH = [[75, 121], [113, 77]];
const K = 0.60 / 192;
const WY = 0.08;
const mapW = ([sx, sy]) => new THREE.Vector3((sx - 120) * K, (88 - sy) * K + WY);

function ribbonXY(p0, p1, color, width, thick = 0.0020, z = 0.0014) {
  const dx = p1.x - p0.x, dy = p1.y - p0.y;
  const len = Math.hypot(dx, dy);
  const g = new THREE.Group();
  g.position.set(p0.x, p0.y, z);
  g.rotation.z = Math.atan2(dy, dx) - Math.PI / 2;
  const m = new THREE.Mesh(new THREE.BoxGeometry(width, len, thick), color);
  m.position.y = len / 2;
  g.add(m);
  g.scale.y = 0.0001;
  brandCard.add(g);
  return g;
}
// The mark is one polyline: each segment is a mitered quad, so the joints are
// exact when the stroke is complete (no notches between separate bars).
const WIDTH = 0.040;
const wPts = W_PATH.map(([sx, sy]) => new THREE.Vector2((sx - 120) * K, (88 - sy) * K + WY));
const wDir = [];
for (let i = 0; i < wPts.length - 1; i++) wDir.push(wPts[i + 1].clone().sub(wPts[i]).normalize());
const wMiter = wPts.map((_, i) => {
  const d0 = wDir[Math.max(0, i - 1)], d1 = wDir[Math.min(wDir.length - 1, i)];
  const n0 = new THREE.Vector2(-d0.y, d0.x), n1 = new THREE.Vector2(-d1.y, d1.x);
  const m = n0.clone().add(n1);
  if (m.lengthSq() < 1e-8) m.copy(n1);
  m.normalize();
  return m.multiplyScalar((WIDTH / 2) / Math.max(0.35, m.dot(n0)));
});

const wSegs = [];
for (let i = 0; i < wPts.length - 1; i++) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(12), 3));
  geo.setIndex([0, 1, 2, 0, 2, 3]);
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: COL.ink, roughness: 0.55, side: THREE.DoubleSide,
  }));
  mesh.visible = false;
  brandCard.add(mesh);
  const start = wPts[i], end = wPts[i + 1];
  const perp = new THREE.Vector2(-wDir[i].y, wDir[i].x).multiplyScalar(WIDTH / 2);
  wSegs.push({
    mesh, geo, start, end, perp,
    startMiter: wMiter[i], endMiter: wMiter[i + 1],
    progress: 0,
  });
}
function updateWSeg(seg, p) {
  const tip = seg.start.clone().lerp(seg.end, p);
  const tipOff = seg.perp.clone().lerp(seg.endMiter, smooth(p));
  const a = seg.start.clone().add(seg.startMiter);
  const b = seg.start.clone().sub(seg.startMiter);
  const c = tip.clone().sub(tipOff);
  const d = tip.clone().add(tipOff);
  const arr = seg.geo.attributes.position.array;
  const z = 0.0014;
  arr[0] = a.x; arr[1] = a.y; arr[2] = z;
  arr[3] = b.x; arr[4] = b.y; arr[5] = z;
  arr[6] = c.x; arr[7] = c.y; arr[8] = z;
  arr[9] = d.x; arr[10] = d.y; arr[11] = z;
  seg.geo.attributes.position.needsUpdate = true;
  seg.geo.computeVertexNormals();
  seg.mesh.visible = p > 0.0005;
}

const wCurrent = ribbonXY(mapW(CURRENT_PATH[0]), mapW(CURRENT_PATH[1]), orangeMat, 0.013, 0.0028, 0.0019);

const cardShadow = new THREE.Mesh(new THREE.PlaneGeometry(1.15, 0.42), new THREE.MeshBasicMaterial({
  map: blobTex, transparent: true, depthWrite: false, opacity: 0,
}));
cardShadow.rotation.x = -Math.PI / 2;
cardShadow.position.set(0, 0.0012, -0.02);
scene.add(cardShadow);

const CARD_START = {
  pos: new THREE.Vector3(0, 0.002, 0.30),
  quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0)),
};
const CARD_END = { pos: new THREE.Vector3(0, 0.32, -0.05), quat: new THREE.Quaternion() };

// ---------------------------------------------------------------- camera
const CAM = [
  { t: 0.0, p: [1.05, 0.80, 1.66], l: [0.20, 0.16, 0.32] },
  { t: 1.5, p: [1.07, 0.80, 1.64], l: [0.20, 0.16, 0.32] },
  { t: 4.0, p: [0.84, 0.62, 1.34], l: [0.00, 0.22, 0.30] },
  { t: 9.0, p: [0.58, 0.56, 1.08], l: [-0.02, 0.21, 0.32] },
  { t: 12.0, p: [0.54, 0.56, 1.06], l: [-0.06, 0.20, 0.34] },
  { t: 14.2, p: [0.50, 0.58, 1.04], l: [-0.14, 0.20, 0.36] },
  { t: 15.4, p: [0.50, 0.72, 1.10], l: [-0.14, 0.20, 0.32] },
  { t: 16.6, p: [0.26, 0.62, 1.12], l: [0.00, 0.16, 0.14] },
  { t: 17.4, p: [0.08, 0.40, 1.07], l: [0.00, 0.30, -0.02] },
  { t: 18.5, p: [0.04, 0.34, 1.04], l: [0.00, 0.31, -0.05] },
  { t: 20.0, p: [0.04, 0.34, 1.04], l: [0.00, 0.31, -0.05] },
];
const tv1 = new THREE.Vector3(), tv2 = new THREE.Vector3();
function cameraAt(t) {
  let i = 0;
  while (i < CAM.length - 2 && t > CAM[i + 1].t) i++;
  const a = CAM[i], b = CAM[i + 1];
  const u = smooth(span(t, a.t, b.t));
  tv1.fromArray(a.p); tv2.fromArray(b.p);
  camera.position.copy(tv1).lerp(tv2, u);
  tv1.fromArray(a.l); tv2.fromArray(b.l);
  camera.lookAt(tv1.lerp(tv2, u));
}

// ---------------------------------------------------------------- post
const composer = new EffectComposer(renderer);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));
const bokeh = new BokehPass(scene, camera, { focus: 1.6, aperture: 0.0011, maxblur: 0.0075 });
composer.addPass(bokeh);
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.24, 0.55, 1.75);
composer.addPass(bloom);
const vignette = new ShaderPass(VignetteShader);
vignette.uniforms.offset.value = 0.95;
vignette.uniforms.darkness.value = 1.02;
composer.addPass(vignette);
composer.addPass(new OutputPass());
const fxaa = new ShaderPass(FXAAShader);
fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
composer.addPass(fxaa);

// ---------------------------------------------------------------- overlay
const $ = id => document.getElementById(id);
const els = { term: $('term'), typed: $('typed'), caret: $('caret'), wordmark: $('wordmark'), tagline: $('tagline') };
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

function panelX(t) {
  return lerp(0, -0.28, smooth(span(t, 12.3, 14.1)));
}

function update(t) {
  cameraAt(t);

  // card / panel
  const px = panelX(t);
  const unfold = smooth(span(t, 5.0, 5.6));
  const lift = t > 5.0 && t < 5.25 ? 0.0018 * Math.sin(Math.PI * span(t, 5.0, 5.25)) : 0;
  card.position.set(px, 0.002 + lift, PANEL.z);
  card.scale.set(lerp(0.26, PANEL.w, unfold), 0.004, lerp(0.18, PANEL.d, unfold));
  card.rotation.z = (t > 12.3 && t < 14.4) ? 0.02 * Math.sin(Math.PI * span(t, 12.3, 14.4)) : 0;
  cardEdge.scale.copy(card.scale);
  cardEdge.position.copy(card.position);
  cardEdge.rotation.copy(card.rotation);
  cardEdge.visible = unfold < 0.98;

  // chart
  const cx = px, cz = PANEL.z;
  const grow = smooth(span(t, 9.0, 11.0));
  curve.visible = t >= 9.0;
  curve.position.set(cx, 0, cz);
  curveGeo.setDrawRange(0, Math.max(0, Math.floor(curveCount * grow)));
  axisX.visible = axisZ.visible = unfold > 0.6;
  axisX.position.set(cx, 0.006, cz + CH.zBase);
  axisZ.position.set(cx + CH.x0, 0.006, cz + CH.zBase - 0.072);
  dots.forEach(d => {
    d.visible = unfold > 0.9 && grow > d.userData.u;
    const p = chartPts(d.userData.u);
    d.position.set(cx + p.x, 0.0095, cz + p.z);
  });
  const idx = Math.min(CH.n, Math.floor(grow * CH.n));
  const p0 = chartPts(idx / CH.n);
  tip.position.set(cx + p0.x, 0.0105, cz + p0.z);
  tip.visible = t >= 9.0 && t < 13.0;
  if (tip.visible) tip.scale.setScalar(1 + 0.18 * Math.sin(Math.PI * span(t, 10.95, 11.25)));

  // ripples
  const r1 = span(t, 5.0, 5.28);
  const r2 = span(t, 8.5, 8.78);
  const r3 = span(t, 14.0, 14.28);
  [[rings[0], r1, -0.20, 0.295], [rings[1], r2, -0.20, 0.295], [rings[2], r3, -0.28 + 0.19, 0.42]]
    .forEach(([m, p, rx, rz]) => {
      m.visible = p > 0 && p < 1;
      if (!m.visible) return;
      m.position.set(rx, 0.0055, rz);
      m.scale.setScalar(1 + 3.0 * p);
      m.material.opacity = 0.85 * (1 - p);
    });

  poseChar(t);

  // brand card: lifts off the desk and stands facing the camera
  const rise = smooth(span(t, 16.4, 17.6));
  brandCard.visible = t >= 16.4;
  brandCard.position.copy(CARD_START.pos).lerp(CARD_END.pos, rise);
  brandCard.quaternion.copy(CARD_START.quat).slerp(CARD_END.quat, rise);
  cardFill.intensity = 0.9 * smooth(span(t, 16.6, 17.8));
  cardShadow.material.opacity = 0.35 * smooth(span(t, 16.8, 17.8));

  const wIn = t - 17.2;
  const win = [[0.00, 0.28], [0.22, 0.50], [0.44, 0.72], [0.66, 0.95]];
  wSegs.forEach((seg, i) => {
    updateWSeg(seg, span(wIn, win[i][0], win[i][1]));
  });
  wCurrent.visible = t >= 19.5;
  wCurrent.scale.y = Math.max(0.0001, span(t, 19.5, 19.7));

  // post focus rides the active subject
  const focusPoint = (t < 8.5) ? hero.position
    : (t < 13.0 ? new THREE.Vector3(px, 0.02, cz) : new THREE.Vector3(0, 0.28, 0.02));
  bokeh.uniforms.focus.value = camera.position.distanceTo(focusPoint);
  bokeh.uniforms.aperture.value = t > 12 && t < 15 ? 0.0014 : 0.0011;

  // overlay
  const typed = Math.floor(clamp01((t - 6.0) / 2.0) * typedFull.length);
  els.typed.textContent = typedFull.slice(0, typed);
  els.typed.className = t >= 8.5 ? 'dim' : '';
  els.caret.style.color = (t >= 5.6 && t < 8.5) ? '#E8733B' : '#6B7280';
  els.caret.style.display = (t >= 5.6 && t < 8.5) ? 'inline' : 'none';
  const termAnchor = new THREE.Vector3(px - 0.19, 0.008, cz - 0.105);
  place(els.term, termAnchor, 0.020, false, t >= 5.6);

  const wmLocal = new THREE.Vector3(0, -0.115, 0.002);
  const tagLocal = new THREE.Vector3(0, -0.175, 0.002);
  place(els.wordmark, brandCard.localToWorld(wmLocal), 0.052, true, t >= 18.4);
  place(els.tagline, brandCard.localToWorld(tagLocal), 0.020, true, t >= 18.4);

  composer.render();
}

window.DUR = DUR;
window.seek = t => { update(t); };

document.fonts.ready.then(() => {
  update(0);
  window.READY = true;
});
