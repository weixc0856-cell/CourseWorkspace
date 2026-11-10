// WAYNE — atelier opener, 20 s.
// Miniature creative atelier: the creator robot works on a sheet on the top
// step; a step response grows on the paper; the sheet lifts into a brand board
// at the window opening. Pure function of t via window.seek(t).

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
  wall: 0xFBFAF7, floor: 0xD8D1C5, graphite: 0x303236, orange: 0xE8733B,
  paper: 0xFBFAF7, ceramic: 0xEFEAE0, stone: 0xE2DACB,
};
const TOP = 0.34;

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

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.02;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(COL.wall);
scene.fog = new THREE.Fog(COL.wall, 6, 16);
const camera = new THREE.PerspectiveCamera(36, W / H, 0.05, 40);

function tex(size, draw, repeat = 1) {
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

const paperTex = tex(512, (g, s) => {
  const rnd = mulberry32(7);
  g.fillStyle = '#FBFAF7'; g.fillRect(0, 0, s, s);
  for (let i = 0; i < 18000; i++) {
    const v = 246 + Math.floor(rnd() * 8);
    g.fillStyle = `rgba(${v},${v - 2},${v - 6},0.45)`;
    g.fillRect(rnd() * s, rnd() * s, 1, 1);
  }
}, 5);

const mat = (color, rough = 0.9, metal = 0) =>
  new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal });
const wallMat = mat(COL.wall, 0.96);
const floorMat = mat(COL.floor, 0.8);
const ceramicMat = mat(COL.ceramic, 0.5);
const stoneMat = mat(COL.stone, 0.72);
const graphiteMat = mat(COL.graphite, 0.4, 0.3);
const orangeMat = mat(COL.orange, 0.35);
const paperMat = new THREE.MeshPhysicalMaterial({
  map: paperTex, color: 0xffffff, roughness: 0.82, sheen: 0.25, sheenRoughness: 0.7,
});

// ---------------------------------------------------------------- light
scene.add(new THREE.HemisphereLight(0xffffff, 0xE8E3D8, 0.6));
const key = new THREE.DirectionalLight(0xfff4e6, 1.6);
key.position.set(-2.4, 3.4, 2.6);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -4; key.shadow.camera.right = 4;
key.shadow.camera.top = 4; key.shadow.camera.bottom = -4;
key.shadow.camera.near = 0.1; key.shadow.camera.far = 12;
key.shadow.bias = -0.0004;
key.shadow.normalBias = 0.02;
key.shadow.radius = 5;
scene.add(key);
const rim = new THREE.DirectionalLight(0xffffff, 1.0);
rim.position.set(2.2, 1.8, -3.0);
scene.add(rim);
const fill = new THREE.DirectionalLight(0xffffff, 0.35);
fill.position.set(0.5, 1.4, 3.2);
scene.add(fill);

// ---------------------------------------------------------------- atelier
function box(size, pos, material, rot = [0, 0, 0], cast = true) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
  m.position.set(...pos);
  m.rotation.set(...rot);
  m.castShadow = cast; m.receiveShadow = true;
  scene.add(m); return m;
}
function cyl(r, h, pos, material, rot = [0, 0, 0]) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, 40), material);
  m.position.set(...pos); m.rotation.set(...rot);
  m.castShadow = m.receiveShadow = true;
  scene.add(m); return m;
}

const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), floorMat);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

box([1.7, 2.4, 0.12], [-2.15, 1.2, -1.7], wallMat);
box([1.7, 2.4, 0.12], [2.15, 1.2, -1.7], wallMat);
box([2.6, 0.55, 0.12], [0, 2.12, -1.7], wallMat);
box([0.12, 2.4, 3.4], [-2.45, 1.2, 0.0], wallMat);
box([2.4, 2.2, 0.1], [0, 1.1, -2.9], mat(0xFBFAF7, 1.0), [0, 0, 0], false);

box([2.6, 0.10, 1.8], [0, 0.05, -0.15], stoneMat, [0, 0, 0], false);
box([1.7, 0.16, 1.1], [-0.15, 0.18, -0.25], ceramicMat, [0, 0, 0], false);
box([1.2, 0.08, 0.78], [0.05, 0.30, -0.30], ceramicMat, [0, 0, 0], false);

// props
const sheet = box([0.36, 0.0016, 0.26], [0.12, TOP + 0.002, -0.24], paperMat, [0, 0.12, 0]);
box([0.30, 0.0016, 0.21], [0.10, TOP + 0.004, -0.22], paperMat, [0, -0.2, 0]);
cyl(0.035, 0.52, [-0.55, 0.26, -0.55], paperMat, [0.10, 0.06, 0]);
cyl(0.028, 0.46, [-0.48, 0.23, -0.48], paperMat, [-0.05, 0.12, 0]);
cyl(0.024, 0.40, [-0.42, 0.20, -0.42], paperMat, [0.06, -0.10, 0]);
box([0.30, 0.006, 0.03], [0.42, TOP + 0.006, -0.06], graphiteMat);
box([0.22, 0.16, 0.16], [-0.85, TOP + 0.08, -0.55], paperMat);
box([0.10, 0.22, 0.10], [-0.78, TOP + 0.11, -0.50], paperMat);
cyl(0.05, 0.12, [-0.30, TOP + 0.06, -0.36], graphiteMat);
cyl(0.0055, 0.19, [-0.305, TOP + 0.105, -0.365], orangeMat, [0.1, 0, 0.05]);
cyl(0.0055, 0.19, [-0.29, TOP + 0.105, -0.35], graphiteMat, [-0.1, 0, -0.05]);
for (let i = 0; i < 5; i++) {
  box([0.26, 0.0016, 0.19], [0.46 + i * 0.002, TOP + 0.004 + i * 0.0017, -0.40 - i * 0.001],
      paperMat, [0, 0.05 * i, 0]);
}
cyl(0.03, 0.022, [0.30, TOP + 0.011, -0.34], mat(0xC97B4E, 0.3, 0.85));

// ---------------------------------------------------------------- chart on the sheet
const CH = { x0: -0.13, x1: 0.13, zBase: 0.055, h: 0.115, n: 64 };
const response = u => 1 - Math.exp(-5.5 * u) * Math.cos(7.5 * u);
const chartPts = u => new THREE.Vector3(
  0.12 + CH.x0 + (CH.x1 - CH.x0) * u, TOP + 0.006, -0.24 + CH.zBase - CH.h * response(u),
);
const pts = [];
for (let i = 0; i <= CH.n; i++) pts.push(chartPts(i / CH.n));
const curveGeo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 140, 0.0018, 8, false);
const curve = new THREE.Mesh(curveGeo, mat(COL.graphite, 0.55));
curve.visible = false; scene.add(curve);
const curveCount = curveGeo.index.count;
const axisMat = mat(0x8A8478, 0.9);
const axisX = new THREE.Mesh(new THREE.BoxGeometry(CH.x1 - CH.x0, 0.001, 0.001), axisMat);
axisX.position.set(0.12, TOP + 0.005, -0.24 + CH.zBase);
const axisZ = new THREE.Mesh(new THREE.BoxGeometry(0.001, 0.001, 0.13), axisMat);
axisZ.position.set(0.12 + CH.x0, TOP + 0.005, -0.24 + CH.zBase - 0.065);
scene.add(axisX, axisZ);
const tip = new THREE.Mesh(new THREE.SphereGeometry(0.005, 14, 10), orangeMat);
tip.visible = false; scene.add(tip);

const rings = [0, 1].map(() => {
  const m = new THREE.Mesh(new THREE.RingGeometry(0.004, 0.0065, 40),
    new THREE.MeshBasicMaterial({ color: COL.orange, transparent: true, opacity: 0, side: THREE.DoubleSide }));
  m.rotation.x = -Math.PI / 2; m.visible = false; scene.add(m); return m;
});

// ---------------------------------------------------------------- character
const data = await fetch('./character.json').then(r => r.json());
const hero = new THREE.Group();
hero.scale.setScalar(0.55);
scene.add(hero);

const vc = m => { const c = m.clone(); c.vertexColors = true; return c; };
const matMap = {
  ceramic: vc(new THREE.MeshPhysicalMaterial({ color: COL.paper, roughness: 0.46, clearcoat: 0.06 })),
  warmgray: vc(new THREE.MeshStandardMaterial({ color: 0xC9C2B4, roughness: 0.6 })),
  graphite: vc(new THREE.MeshStandardMaterial({ color: 0x2A2E33, roughness: 0.42, metalness: 0.35 })),
  copper: vc(new THREE.MeshStandardMaterial({ color: 0xC97B4E, roughness: 0.3, metalness: 0.85 })),
  visor: vc(new THREE.MeshPhysicalMaterial({ color: 0x0B0E12, roughness: 0.14, metalness: 0.1, clearcoat: 1 })),
  eye: vc(new THREE.MeshStandardMaterial({ color: 0xFF6A2A, emissive: 0xFF5A1E, emissiveIntensity: 1.5, roughness: 0.3 })),
  orange: vc(new THREE.MeshStandardMaterial({ color: COL.orange, roughness: 0.4 })),
};
const nodes = {};
const groups = {};
for (const g of data.groups) groups[g.name] = { grp: new THREE.Group(), pivot: new THREE.Vector3(...g.pivot) };
for (const g of data.groups) {
  const parent = g.parent === 'Root' ? hero : groups[g.parent].grp;
  const pp = g.parent === 'Root' ? new THREE.Vector3() : groups[g.parent].pivot;
  parent.add(groups[g.name].grp);
  groups[g.name].grp.position.copy(groups[g.name].pivot).sub(pp);
}
for (const p of data.parts) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(p.positions, 3));
  geo.setAttribute('normal', new THREE.Float32BufferAttribute(p.normals, 3));
  geo.setIndex(p.indices);
  if (p.colors) geo.setAttribute('color', new THREE.Float32BufferAttribute(p.colors, 3));
  const mesh = new THREE.Mesh(geo, matMap[p.mat] || matMap.ceramic);
  mesh.name = p.name;
  mesh.castShadow = mesh.receiveShadow = true;
  nodes[p.name] = mesh;
  const grp = groups[p.group];
  mesh.position.copy(new THREE.Vector3(...p.pivot)).sub(grp.pivot);
  grp.grp.add(mesh);
}
const bodyG = groups.Body.grp, headG = groups.Head.grp;
const shL = groups.ShoulderL.grp, shR = groups.ShoulderR.grp;
const elL = groups.ElbowL.grp, elR = groups.ElbowR.grp;
const hipL = groups.HipL.grp, hipR = groups.HipR.grp;
const kneeL = groups.KneeL.grp, kneeR = groups.KneeR.grp;
const eyeL = nodes.EyeL, eyeR = nodes.EyeR;

// ---------------------------------------------------------------- board + mark
const board = new THREE.Group();
scene.add(board);
board.visible = false;
const boardFace = new THREE.Mesh(new THREE.PlaneGeometry(1.55, 0.92), paperMat);
board.add(boardFace);
board.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.PlaneGeometry(1.55, 0.92)),
  new THREE.LineBasicMaterial({ color: 0xE3E0D7 })));

const W_PATH = [[24, 44], [66, 132], [120, 68], [174, 132], [216, 44]];
const CURRENT = [[75, 121], [113, 77]];
const K = 1.10 / 192, WY = 0.06;
const mapW = ([sx, sy]) => new THREE.Vector2((sx - 120) * K, (88 - sy) * K + WY);

const WIDTH = 0.085;
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
function wSeg(p0, p1, color, width, z = 0.0014) {
  const g = new THREE.Group();
  g.position.set(p0.x, p0.y, z);
  g.rotation.z = Math.atan2(p1.y - p0.y, p1.x - p0.x) - Math.PI / 2;
  const len = p0.distanceTo(p1);
  const m = new THREE.Mesh(new THREE.BoxGeometry(width, len, 0.002), color);
  m.position.y = len / 2;
  g.add(m); g.scale.y = 0.0001; g.visible = false;
  board.add(g); return g;
}
const wSegs = [];
for (let i = 0; i < wPts.length - 1; i++) {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(12), 3));
  geo.setIndex([0, 1, 2, 0, 2, 3]);
  const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
    color: COL.graphite, roughness: 0.6, side: THREE.DoubleSide,
  }));
  mesh.visible = false;
  board.add(mesh);
  wSegs.push({
    mesh, geo, start: wPts[i], end: wPts[i + 1],
    perp: new THREE.Vector2(-wDir[i].y, wDir[i].x).multiplyScalar(WIDTH / 2),
    startMiter: wMiter[i], endMiter: wMiter[i + 1],
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
const wCurrent = wSeg(mapW(CURRENT[0]), mapW(CURRENT[1]), orangeMat, 0.028, 0.0019);

const BOARD_START = { pos: new THREE.Vector3(0, 0.02, -1.00), quat: new THREE.Quaternion().setFromEuler(new THREE.Euler(-Math.PI / 2, 0, 0)) };
const BOARD_END = { pos: new THREE.Vector3(0, 0.47, -1.55), quat: new THREE.Quaternion() };

// ---------------------------------------------------------------- camera
const CAM = [
  { t: 0.0, p: [2.60, 1.55, 2.90], l: [0.0, 0.60, -0.60] },
  { t: 4.0, p: [1.90, 1.15, 2.00], l: [0.05, 0.55, -0.35] },
  { t: 7.0, p: [1.3, 0.90, 1.35], l: [0.10, 0.50, -0.28] },
  { t: 10.0, p: [1.10, 0.85, 1.10], l: [0.05, 0.50, -0.28] },
  { t: 13.0, p: [1.00, 0.85, 1.05], l: [0.00, 0.55, -0.45] },
  { t: 15.5, p: [0.90, 0.95, 0.90], l: [0.00, 0.60, -0.90] },
  { t: 17.0, p: [0.18, 0.62, 0.42], l: [0.00, 0.54, -1.30] },
  { t: 18.5, p: [0.00, 0.50, 0.06], l: [0.00, 0.50, -1.55] },
  { t: 20.0, p: [0.00, 0.50, 0.06], l: [0.00, 0.50, -1.55] },
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
const bokeh = new BokehPass(scene, camera, { focus: 2.0, aperture: 0.0012, maxblur: 0.008 });
composer.addPass(bokeh);
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.22, 0.55, 1.8);
composer.addPass(bloom);
const vignette = new ShaderPass(VignetteShader);
vignette.uniforms.offset.value = 0.96;
vignette.uniforms.darkness.value = 1.04;
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
  return { x: (v3.x * 0.5 + 0.5) * W, y: (-v3.y * 0.5 + 0.5) * H };
}
function ppm(p) {
  const a = screenOf(p);
  const b = screenOf(v3.copy(p).add(new THREE.Vector3(0.1, 0, 0)));
  return Math.hypot(b.x - a.x, b.y - a.y) / 0.1;
}
function place(el, p, h, centered, visible) {
  if (!visible) { el.style.display = 'none'; return; }
  const s = screenOf(p);
  el.style.display = 'block';
  el.style.fontSize = `${Math.max(8, ppm(p) * h).toFixed(2)}px`;
  el.style.transform = centered
    ? `translate(${s.x.toFixed(2)}px, ${s.y.toFixed(2)}px) translate(-50%, -50%)`
    : `translate(${s.x.toFixed(2)}px, ${s.y.toFixed(2)}px) translate(0, -50%)`;
}

// ---------------------------------------------------------------- character motion
function charState(t) {
  let x = 1.30, z = -0.10, y = 0, yaw = -1.3, lean = 0, swingR = 0, swingL = 0, stepL = 0, stepR = 0;

  if (t < 0.8) return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR };
  if (t < 1.6) {                                  // entry hop
    const p = smooth(span(t, 0.8, 1.6));
    x = lerp(1.30, -0.04, p); z = lerp(-0.10, -0.20, p);
    y = 0.22 * Math.sin(Math.PI * p);
    yaw = lerp(-1.3, -0.4, p);
    stepL = stepR = 0.5 * Math.sin(Math.PI * p);
    return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR };
  }
  x = -0.04; z = -0.20;
  const face = (tx, tz) => Math.atan2(tx - x, tz - z);
  if (t < 3.0) { yaw = lerp(-0.4, face(0.1, -0.25), smooth(span(t, 1.6, 2.2))); }
  else if (t < 4.0) { yaw = face(0.1, -0.25) + 0.35 * Math.sin(Math.PI * 2 * (t - 3.0) / 2.0); }
  else if (t < 5.0) {                             // walk to the sheet
    const p = smooth(span(t, 4.0, 4.8));
    x = lerp(-0.04, -0.08, p); z = lerp(-0.20, -0.245, p);
    y = 0.05 * Math.sin(Math.PI * p);
    yaw = face(0.12, -0.24);
    stepL = 0.3 * Math.sin(Math.PI * 2 * (t - 4.0) / 0.45);
    stepR = -stepL;
  } else if (t < 5.6) {                           // tap
    x = -0.08; z = -0.245; yaw = face(0.12, -0.24);
    lean = 0.10;
    const p = Math.sin(Math.PI * span(t, 5.0, 5.25));
    swingR = -1.2 * p;
  } else if (t < 6.2) {                           // step back
    const p = smooth(span(t, 5.6, 6.1));
    x = lerp(-0.08, -0.02, p); z = lerp(-0.245, -0.22, p);
    y = 0.03 * Math.sin(Math.PI * span(t, 5.6, 6.0));
    yaw = face(0.12, -0.24); lean = 0.10 * (1 - p);
  } else if (t < 9.0) {                           // typing
    x = -0.02; z = -0.22; yaw = face(0.12, -0.24); lean = 0.05;
    const k = 1 - Math.abs(((t - 6.2) / 0.5 % 1) * 2 - 1);
    swingR = -0.16 - 0.1 * k;
  } else if (t < 9.4) {                           // enter
    x = -0.02; z = -0.22; yaw = face(0.12, -0.24);
    const p = Math.sin(Math.PI * span(t, 9.0, 9.3));
    swingR = -0.85 * p; lean = 0.05 + 0.05 * p;
  } else if (t < 13.0) {                          // watch the curve
    x = -0.02; z = -0.22; yaw = face(0.12, -0.24);
    lean = -0.06 * smooth(span(t, 10.0, 12.0));
  } else if (t < 14.6) {                          // hop right, out of the board's way
    const p = smooth(span(t, 13.0, 14.5));
    x = lerp(-0.02, 0.58, p); z = lerp(-0.22, -0.18, p);
    y = 0.06 * Math.sin(Math.PI * span(t, 13.0, 13.55)) + 0.06 * Math.sin(Math.PI * span(t, 13.75, 14.3));
    yaw = lerp(face(0.12, -0.24), 0.35, p);
  } else {                                        // stands and watches the mark
    x = 0.58; z = -0.18; yaw = 0.35;
  }
  return { x, z, y, yaw, lean, swingR, swingL, stepL, stepR };
}

const landing = [1.6, 5.6, 13.0, 14.3];

function poseChar(t) {
  const s = charState(t);
  hero.position.set(s.x, TOP + s.y, s.z);
  hero.rotation.y = s.yaw;
  bodyG.rotation.x = s.lean;
  headG.rotation.x = -0.3 * s.lean;
  let sq = 0;
  for (const tl of landing) {
    const d = t - tl;
    if (d >= 0 && d < 0.2) sq = Math.max(sq, 0.10 * Math.sin(Math.PI * d / 0.2));
  }
  const breath = 1 + 0.004 * Math.sin((Math.PI * 2 * t) / 2.4);
  bodyG.scale.set(1 + 0.05 * sq, (1 - sq) * breath, 1 + 0.05 * sq);
  shL.rotation.x = s.swingL; shR.rotation.x = s.swingR;
  elL.rotation.x = -0.35 * s.swingL; elR.rotation.x = -0.35 * s.swingR;
  hipL.rotation.x = s.stepL; hipR.rotation.x = s.stepR;
  kneeL.rotation.x = -0.45 * s.stepL; kneeR.rotation.x = -0.45 * s.stepR;
  const blink = (t % 3.2) < 0.12 ? 0.15 : 1;
  if (eyeL) eyeL.scale.y = blink;
  if (eyeR) eyeR.scale.y = blink;
  return s;
}

// ---------------------------------------------------------------- update
const typedFull = '$ render lesson';

function update(t) {
  cameraAt(t);

  const grow = smooth(span(t, 10.0, 12.0));
  curve.visible = t >= 10.0;
  curveGeo.setDrawRange(0, Math.max(0, Math.floor(curveCount * grow)));
  axisX.visible = axisZ.visible = t >= 6.0;
  const idx = Math.min(CH.n, Math.floor(grow * CH.n));
  const p0 = chartPts(idx / CH.n);
  tip.position.copy(p0);
  tip.visible = t >= 10.0 && t < 12.6;

  const r1 = span(t, 5.0, 5.3);
  const r2 = span(t, 9.0, 9.3);
  [[rings[0], r1, 0.22, -0.25], [rings[1], r2, 0.22, -0.25]].forEach(([m, p, rx, rz]) => {
    m.visible = p > 0 && p < 1;
    if (!m.visible) return;
    m.position.set(rx, TOP + 0.004, rz);
    m.scale.setScalar(1 + 3.0 * p);
    m.material.opacity = 0.85 * (1 - p);
  });

  poseChar(t);

  const rise = smooth(span(t, 13.4, 15.4));
  board.visible = t >= 13.4;
  board.position.copy(BOARD_START.pos).lerp(BOARD_END.pos, rise);
  board.quaternion.copy(BOARD_START.quat).slerp(BOARD_END.quat, rise);

  const wIn = t - 15.5;
  const win = [[0.0, 0.28], [0.22, 0.5], [0.44, 0.72], [0.66, 0.95]];
  wSegs.forEach((seg, i) => {
    updateWSeg(seg, span(wIn, win[i][0], win[i][1]));
  });
  wCurrent.visible = t >= 18.4;
  wCurrent.scale.y = Math.max(0.0001, span(t, 18.4, 18.6));

  const focus = t < 9 ? new THREE.Vector3(hero.position.x, TOP + 0.2, hero.position.z)
    : (t < 13 ? new THREE.Vector3(0.12, TOP + 0.05, -0.24) : new THREE.Vector3(0, 0.5, -1.5));
  bokeh.uniforms.focus.value = camera.position.distanceTo(focus);

  const typed = Math.floor(clamp01((t - 6.2) / 2.4) * typedFull.length);
  els.typed.textContent = typedFull.slice(0, typed);
  els.typed.className = t >= 9.0 ? 'dim' : '';
  els.caret.style.color = (t >= 6.0 && t < 9.0) ? '#E8733B' : '#6B7280';
  els.caret.style.display = (t >= 6.0 && t < 9.0) ? 'inline' : 'none';
  place(els.term, new THREE.Vector3(0.02, TOP + 0.012, -0.30), 0.016, false, t >= 6.0);

  const wm = board.localToWorld(new THREE.Vector3(0, -0.30, 0.002));
  const tag = board.localToWorld(new THREE.Vector3(0, -0.395, 0.002));
  place(els.wordmark, wm, 0.080, true, t >= 17.6);
  place(els.tagline, tag, 0.028, true, t >= 17.6);

  composer.render();
}

window.DUR = DUR;
window.seek = t => update(t);
document.fonts.ready.then(() => { update(0); window.READY = true; });
