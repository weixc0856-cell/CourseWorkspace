// Aging-evolution world: agent-based simulation + hazard overlay, pure f(t).
import * as THREE from './three.module.js';
import { EffectComposer } from './vendor/three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/three/addons/postprocessing/RenderPass.js';
import { BokehPass } from './vendor/three/addons/postprocessing/BokehPass.js';
import { UnrealBloomPass } from './vendor/three/addons/postprocessing/UnrealBloomPass.js';
import { FilmPass } from './vendor/three/addons/postprocessing/FilmPass.js';
import { ShaderPass } from './vendor/three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from './vendor/three/addons/postprocessing/OutputPass.js';
import { ColorCorrectionShader } from './vendor/three/addons/shaders/ColorCorrectionShader.js';
import { VignetteShader } from './vendor/three/addons/shaders/VignetteShader.js';
import { FXAAShader } from './vendor/three/addons/shaders/FXAAShader.js';

const W = window.innerWidth;
const H = window.innerHeight;
const PANEL = Math.min(430, Math.round(W * 0.31));

const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x1d2226, 0.020);

const camera = new THREE.PerspectiveCamera(34, W / H, 0.1, 200);
camera.setViewOffset(W, H, Math.round(W * 0.14), 0, W, H);
const look = new THREE.Vector3(0, 0.2, 0);

// Post chain — all official three.js r160 addons (see vendor/three/README.md):
// depth of field, bloom, colour correction, film grain, vignette, ACES output
// and FXAA. No hand-written shaders.
const composer = new EffectComposer(renderer);
composer.setPixelRatio(1);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));

const bokeh = new BokehPass(scene, camera, {focus: 14.0, aperture: 0.0004, maxblur: 0.006});
composer.addPass(bokeh);

const bloom = new UnrealBloomPass(new THREE.Vector2(W * 0.5, H * 0.5), 0.28, 0.4, 1.8);
composer.addPass(bloom);

const grade = new ShaderPass(ColorCorrectionShader);
grade.uniforms.powRGB.value.set(1.02, 1.02, 1.02);
grade.uniforms.mulRGB.value.set(1.03, 1.0, 0.965);
grade.uniforms.addRGB.value.set(0.0, 0.0006, 0.0016);
composer.addPass(grade);

const grain = new FilmPass(0.05, false);
composer.addPass(grain);

const vignette = new ShaderPass(VignetteShader);
vignette.uniforms.offset.value = 0.9;
vignette.uniforms.darkness.value = 0.95;
composer.addPass(vignette);

composer.addPass(new OutputPass());

const fxaa = new ShaderPass(FXAAShader);
fxaa.uniforms.resolution.value.set(1 / W, 1 / H);
composer.addPass(fxaa);

// dome
const domeGeo = new THREE.SphereGeometry(90, 32, 16);
const top = new THREE.Color(0x39434b);
const bottom = new THREE.Color(0x121619);
const colors = [];
const pos = domeGeo.attributes.position;
for (let i = 0; i < pos.count; i += 1) {
  const v = Math.min(1, Math.max(0, (pos.getY(i) / 90 + 0.2) / 0.95));
  const c = bottom.clone().lerp(top, v);
  colors.push(c.r, c.g, c.b);
}
domeGeo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
scene.add(new THREE.Mesh(domeGeo, new THREE.MeshBasicMaterial({vertexColors: true, side: THREE.BackSide, depthWrite: false, fog: false})));

// terrain: a shallow basin that rises away from the plateau
function terrainHeight(x, z) {
  const r = Math.hypot(x, z);
  const edge = Math.min(1, Math.max(0, (r - 7) / 9));
  const wave = 0.55 * Math.sin(x * 0.42) + 0.45 * Math.cos(z * 0.37) + 0.5;
  return edge * wave * 0.28;
}

const terrainGeometry = new THREE.PlaneGeometry(64, 42, 96, 64).rotateX(-Math.PI / 2);
const terrainPosition = terrainGeometry.attributes.position;
for (let i = 0; i < terrainPosition.count; i += 1) {
  terrainPosition.setY(i, terrainHeight(terrainPosition.getX(i), terrainPosition.getZ(i)));
}
terrainGeometry.computeVertexNormals();
const ground = new THREE.Mesh(
  terrainGeometry,
  new THREE.MeshStandardMaterial({color: 0x1e2429, roughness: 1, metalness: 0})
);
ground.position.set(0, -0.02, 0);
ground.receiveShadow = true;
scene.add(ground);

const grid = new THREE.GridHelper(24, 24, 0x3a4650, 0x2a3238);
grid.position.set(0, 0.0, 0);
grid.material.opacity = 0.18;
grid.material.transparent = true;
scene.add(grid);

let rockSeed = 2024;
function rockRand() {
  rockSeed = (rockSeed * 1664525 + 1013904223) >>> 0;
  return rockSeed / 4294967296;
}
const rockGeometry = new THREE.DodecahedronGeometry(0.22, 0);
const rockMaterial = new THREE.MeshStandardMaterial({color: 0x2b3238, roughness: 0.95});
const rocks = new THREE.InstancedMesh(rockGeometry, rockMaterial, 46);
rocks.castShadow = true;
rocks.receiveShadow = true;
const rockDummy = new THREE.Object3D();
for (let i = 0; i < 46; i += 1) {
  const angle = rockRand() * Math.PI * 2;
  const radius = 8.5 + rockRand() * 9.0;
  const x = Math.cos(angle) * radius;
  const z = Math.sin(angle) * radius;
  rockDummy.position.set(x, terrainHeight(x, z) + 0.08, z);
  rockDummy.rotation.set(rockRand() * 2, rockRand() * 3, rockRand() * 2);
  const size = 0.6 + rockRand() * 0.9;
  rockDummy.scale.set(size, size * 0.8, size);
  rockDummy.updateMatrix();
  rocks.setMatrixAt(i, rockDummy.matrix);
}
scene.add(rocks);

// lights
scene.add(new THREE.HemisphereLight(0xa9bccb, 0x161a1d, 1.0));
const key = new THREE.DirectionalLight(0xfff0dd, 2.3);
key.position.set(8, 16, -8);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -12;
key.shadow.camera.right = 12;
key.shadow.camera.top = 12;
key.shadow.camera.bottom = -12;
key.shadow.camera.near = 1;
key.shadow.camera.far = 60;
key.shadow.bias = -0.0006;
key.shadow.normalBias = 0.02;
scene.add(key);
const rim = new THREE.DirectionalLight(0x7fb0c8, 0.9);
rim.position.set(-10, 8, 10);
scene.add(rim);

// data
const data = await (await fetch('./aging.json')).json();
const timing = await (await fetch('./timing.json')).json().catch(() => null);
const DURATION = Number(window.DUR || (timing && timing.total) || 150);
const splitTime = (() => {
  if (!timing || !timing.segments) return DURATION * 0.52;
  const safe = timing.segments.find((segment) => segment.id === 's08');
  return safe ? safe.start : DURATION * 0.52;
})();

const AGE_YOUNG = new THREE.Color(0x6e8f6a);
const AGE_OLD = new THREE.Color(0xc06a3a);
const MAX_AGENTS = 200;

// ---- creature --------------------------------------------------------------
// A low-poly quadruped: capsule body, haunch, head with snout and ears, tapered
// tail, two-segment legs, eyes and mutation dots. Each part is one InstancedMesh
// so a field of 190 creatures stays at roughly ten draw calls. Motion is derived
// from the recorded track (speed, heading, age) — the simulation carries no
// behaviour flags, so foraging is a visual idiom, not a modelled variable.
const bodyMat = new THREE.MeshStandardMaterial({roughness: 0.55, metalness: 0.0});
const legMat = new THREE.MeshStandardMaterial({color: 0x39424a, roughness: 0.75});
const eyeMat = new THREE.MeshStandardMaterial({color: 0x0b0b0d, roughness: 0.3});
const maMat = new THREE.MeshStandardMaterial({color: 0x2a2d31, roughness: 0.4});
const ringMat = new THREE.MeshBasicMaterial({color: 0xa8cfb4, transparent: true, opacity: 0.22, depthWrite: false});

const bodyGeo = new THREE.CapsuleGeometry(0.155, 0.26, 5, 12).rotateX(Math.PI / 2);
bodyGeo.scale(1.0, 0.92, 1.0);
const haunchGeo = new THREE.IcosahedronGeometry(0.155, 2);
haunchGeo.scale(1.0, 0.95, 0.9);
const headGeo = new THREE.IcosahedronGeometry(0.115, 2);
headGeo.scale(1.0, 0.92, 1.12);
const snoutGeo = new THREE.IcosahedronGeometry(0.055, 2);
snoutGeo.scale(0.95, 0.72, 1.05);
const earGeo = new THREE.ConeGeometry(0.045, 0.13, 6);
const tailGeo = new THREE.ConeGeometry(0.05, 0.24, 6).rotateX(-Math.PI / 2);
const upperLegGeo = new THREE.CylinderGeometry(0.036, 0.045, 0.125, 6);
const lowerLegGeo = new THREE.CylinderGeometry(0.026, 0.032, 0.115, 6);
const eyeGeo = new THREE.IcosahedronGeometry(0.030, 1);
const maGeo = new THREE.IcosahedronGeometry(0.018, 1);
const ringGeo = new THREE.RingGeometry(0.17, 0.23, 24).rotateX(-Math.PI / 2);
const shadowGeo = new THREE.CircleGeometry(0.30, 18).rotateX(-Math.PI / 2);
const shadowMat = new THREE.MeshBasicMaterial({color: 0x101214, transparent: true, opacity: 0.22, depthWrite: false});

function instanced(geo, mat, count, cast = true) {
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.castShadow = cast;
  mesh.count = 0;
  scene.add(mesh);
  return mesh;
}

const bodies = instanced(bodyGeo, bodyMat, MAX_AGENTS);
const haunches = instanced(haunchGeo, bodyMat, MAX_AGENTS);
const heads = instanced(headGeo, bodyMat, MAX_AGENTS);
const snouts = instanced(snoutGeo, bodyMat, MAX_AGENTS);
const ears = instanced(earGeo, bodyMat, MAX_AGENTS * 2);
const tails = instanced(tailGeo, bodyMat, MAX_AGENTS);
const upperLegs = instanced(upperLegGeo, legMat, MAX_AGENTS * 4);
const lowerLegs = instanced(lowerLegGeo, legMat, MAX_AGENTS * 4);
const eyes = instanced(eyeGeo, eyeMat, MAX_AGENTS * 2, false);
const maDots = instanced(maGeo, maMat, MAX_AGENTS * 4, false);
const rings = instanced(ringGeo, ringMat, MAX_AGENTS, false);
const blobs = instanced(shadowGeo, shadowMat, MAX_AGENTS, false);
const COLOURED = [bodies, haunches, heads, snouts, ears, tails];
for (const mesh of COLOURED) {
  mesh.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(mesh.instanceMatrix.count * 3), 3);
}

const dummy = new THREE.Object3D();
const agentMatrix = new THREE.Matrix4();
const headMatrix = new THREE.Matrix4();
const partMatrix = new THREE.Matrix4();
const quatY = new THREE.Quaternion();
const agentPos = new THREE.Vector3();
const agentScale = new THREE.Vector3();
const Y_AXIS = new THREE.Vector3(0, 1, 0);
const colourScratch = new THREE.Color();

// Attach a part to a parent matrix (agent root or neck pivot).
function placeOn(parent, mesh, slot, px, py, pz, rx = 0, ry = 0, rz = 0, sx = 1, sy = 1, sz = 1) {
  dummy.position.set(px, py, pz);
  dummy.rotation.set(rx, ry, rz);
  dummy.scale.set(sx, sy, sz);
  dummy.updateMatrix();
  partMatrix.multiplyMatrices(parent, dummy.matrix);
  mesh.setMatrixAt(slot, partMatrix);
}

const place = (mesh, slot, ...args) => placeOn(agentMatrix, mesh, slot, ...args);

function pivotMatrix(parent, px, py, pz, rx, ry, rz) {
  dummy.position.set(px, py, pz);
  dummy.rotation.set(rx, ry, rz);
  dummy.scale.set(1, 1, 1);
  dummy.updateMatrix();
  headMatrix.multiplyMatrices(parent, dummy.matrix);
  return headMatrix;
}

function scenarioAt(t) {
  return t < splitTime ? data.scenarios[0] : data.scenarios[1];
}

function localTime(t) {
  return t < splitTime ? t : t - splitTime;
}

function scenarioDuration(t) {
  return t < splitTime ? splitTime : DURATION - splitTime;
}

function updateCamera(t) {
  const u = Math.min(1, Math.max(0, t / DURATION));
  const angle = -1.25 + 0.55 * u;
  const radius = 14.0 - 1.6 * Math.sin(Math.PI * u);
  camera.position.set(Math.cos(angle) * radius, 8.8 - 1.0 * u, Math.sin(angle) * radius);
  camera.lookAt(look);
}

function update(t) {
  const scenario = scenarioAt(t);
  const frames = scenario.frames;
  const local = localTime(t);
  const progress = Math.min(1, Math.max(0, local / Math.max(0.001, scenarioDuration(t))));
  const exact = progress * (frames.length - 1);
  const index = Math.min(frames.length - 1, Math.floor(exact));
  const next = Math.min(frames.length - 1, index + 1);
  const mix = exact - index;
  const frameCur = frames[index];
  const frameNext = frames[next];
  const cur = new Map(frameCur.agents.map((entry) => [entry[0], entry]));
  const nxt = new Map(frameNext.agents.map((entry) => [entry[0], entry]));
  const prv = index > 0
    ? new Map(frames[index - 1].agents.map((entry) => [entry[0], entry]))
    : cur;
  const frameDt = Math.max(0.001, scenarioDuration(t) / Math.max(1, frames.length - 1));

  let count = 0;
  let maCount = 0;
  let ringCount = 0;
  let earCount = 0;
  let eyeCount = 0;
  let legCount = 0;

  for (const agent of cur.values()) {
    const id = agent[0];
    const after = nxt.get(id);
    const aliveNow = agent[4] === 1;
    const aliveNext = after ? after[4] === 1 : aliveNow;
    const fade = !aliveNow ? 0 : aliveNext ? 1 : 1 - Math.min(1, mix * 1.6);
    if (fade <= 0.02) continue;

    const ax = agent[1] + ((after ? after[1] : agent[1]) - agent[1]) * mix;
    const ay = agent[2] + ((after ? after[2] : agent[2]) - agent[2]) * mix;
    const wx = ax;
    const wz = -ay;

    // Heading follows the recorded motion; still creatures keep a stable
    // id-hashed heading rather than snapping to face the camera.
    const from = prv.get(id) || agent;
    const to = after || agent;
    const dx = to[1] - from[1];
    const dy = to[2] - from[2];
    const travel = Math.hypot(dx, dy);
    const yaw = travel > 0.02
      ? Math.atan2(dx, -dy)
      : ((Math.sin(id * 12.9898) * 43758.5453) % 1) * Math.PI * 2;
    const speed = travel / frameDt;

    const age = agent[3];
    const born = age < 2 && index > 0 && !prv.has(id);
    const spawnScale = born ? 0.35 + 0.65 * Math.min(1, mix * 2.2) : 1;
    const scale = (0.85 + 0.010 * age) * fade * spawnScale;

    agentPos.set(wx, 0, wz);
    quatY.setFromAxisAngle(Y_AXIS, yaw);
    agentScale.set(scale, scale, scale);
    agentMatrix.compose(agentPos, quatY, agentScale);

    const move = Math.min(1, speed / 2.2);
    const cadence = Math.min(14, Math.max(1.2, (2 * Math.PI * speed) / 0.55));
    const phase = t * cadence + id * 0.7;
    const swing = 0.30 + 0.42 * move;
    const bob = 0.012 * Math.sin(phase * 2) * move + 0.006 * Math.sin(t * 1.7 + id * 0.9);
    // Grazing: a visual idiom for a nearly still creature, not a modelled variable.
    const graze = Math.max(0, 1 - move * 2.5) * (0.5 + 0.5 * Math.sin(t * 0.8 + id * 1.7));

    const colour = colourScratch.copy(AGE_YOUNG).lerp(AGE_OLD, Math.min(1, age / 80));
    bodies.setColorAt(count, colour);
    haunches.setColorAt(count, colour);
    heads.setColorAt(count, colour);
    snouts.setColorAt(count, colour);
    tails.setColorAt(count, colour);
    ears.setColorAt(earCount, colour);
    ears.setColorAt(earCount + 1, colour);

    place(bodies, count, 0, 0.300 + bob, 0.0);
    place(haunches, count, 0, 0.305 + bob, -0.15);
    place(blobs, count, 0, 0.004, 0);

    // The head hangs off a neck pivot, so the graze dip rotates from the shoulders.
    const headPitch = -0.05 - 0.70 * graze + 0.04 * Math.sin(phase + 1);
    pivotMatrix(agentMatrix, 0, 0.300 + bob, 0.22, headPitch, 0, 0);
    placeOn(headMatrix, heads, count, 0, 0.045, 0.105);
    placeOn(headMatrix, snouts, count, 0, 0.020, 0.230);
    placeOn(headMatrix, ears, earCount, -0.058, 0.125, 0.045, -0.18, 0, 0.30);
    placeOn(headMatrix, ears, earCount + 1, 0.058, 0.125, 0.045, -0.18, 0, -0.30);
    placeOn(headMatrix, eyes, eyeCount, -0.048, 0.058, 0.202);
    placeOn(headMatrix, eyes, eyeCount + 1, 0.048, 0.058, 0.202);
    earCount += 2;
    eyeCount += 2;

    place(tails, count, 0, 0.315 + bob, -0.30,
      -0.55 + 0.18 * Math.sin(t * 2.1 + id),
      0.22 * Math.sin(t * 1.7 + id * 0.7), 0);

    const LEGS = [
      [-0.095, 0.155, 0],
      [0.095, 0.155, Math.PI],
      [-0.095, -0.155, Math.PI],
      [0.095, -0.155, 0],
    ];
    for (let leg = 0; leg < 4; leg += 1) {
      const [lx, lz, offset] = LEGS[leg];
      const hip = swing * Math.sin(phase + offset);
      const knee = 0.55 * move * Math.max(0, -Math.sin(phase + offset + 0.9));
      const hipY = 0.240;
      place(upperLegs, legCount, lx,
        hipY - 0.0625 * Math.cos(hip), lz - 0.0625 * Math.sin(hip), hip, 0, 0);
      const kneeY = hipY - 0.125 * Math.cos(hip);
      const kneeZ = lz - 0.125 * Math.sin(hip);
      place(lowerLegs, legCount, lx,
        kneeY - 0.0575 * Math.cos(hip + knee), kneeZ - 0.0575 * Math.sin(hip + knee), hip + knee, 0, 0);
      legCount += 1;
    }

    const mutations = Math.min(4, agent[5]);
    for (let dot = 0; dot < mutations; dot += 1) {
      const ang = (dot / 4) * Math.PI * 2 + id * 0.6;
      place(maDots, maCount, Math.cos(ang) * 0.075, 0.440 + bob, -0.05 + Math.sin(ang) * 0.10);
      maCount += 1;
    }

    if (born) {
      const grow = 0.5 + 0.7 * Math.min(1, mix * 1.4);
      place(rings, ringCount, 0, 0.012, 0, 0, 0, 0, grow, 1, grow);
      ringCount += 1;
    }
    count += 1;
  }

  bodies.count = count;
  haunches.count = count;
  heads.count = count;
  snouts.count = count;
  tails.count = count;
  blobs.count = count;
  ears.count = earCount;
  eyes.count = eyeCount;
  upperLegs.count = legCount;
  lowerLegs.count = legCount;
  maDots.count = maCount;
  rings.count = ringCount;
  for (const mesh of [bodies, haunches, heads, snouts, ears, tails, upperLegs,
    lowerLegs, eyes, maDots, rings, blobs]) {
    mesh.instanceMatrix.needsUpdate = true;
  }
  for (const mesh of COLOURED) mesh.instanceColor.needsUpdate = true;

  updateCamera(t);
  // Focus rides the world centre; grain is keyed to t so the plate stays a
  // pure function of time (FilmPass would otherwise accumulate its own clock).
  bokeh.uniforms.focus.value = camera.position.distanceTo(look);
  grain.uniforms.time.value = t;
  composer.render(0);
  drawOverlay(t, scenario, frames[index], progress);
}

// ---- overlay ---------------------------------------------------------------
const overlay = document.getElementById('hud');
const chart = document.getElementById('chart');
const ctx = chart.getContext('2d');
const labelEl = document.getElementById('scenario');
const popEl = document.getElementById('pop');
const ageEl = document.getElementById('meanage');
const maEl = document.getElementById('maloci');

function fitChart() {
  const ratio = window.devicePixelRatio || 1;
  chart.width = chart.clientWidth * ratio;
  chart.height = chart.clientHeight * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function drawOverlay(t, scenario, frame, progress) {
  labelEl.textContent = scenario.label;
  labelEl.className = scenario.id;
  popEl.textContent = String(frame.population);
  ageEl.textContent = frame.mean_death_age == null ? '—' : String(Math.round(frame.mean_death_age));
  const alive = frame.agents.filter((agent) => agent[4]);
  const ma = alive.length ? alive.reduce((sum, agent) => sum + agent[5], 0) / alive.length : 0;
  maEl.textContent = ma.toFixed(1);

  const w = chart.clientWidth;
  const h = chart.clientHeight;
  ctx.clearRect(0, 0, w, h);
  ctx.strokeStyle = 'rgba(160,175,186,0.25)';
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = (h * i) / 4;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }
  const hazard = frame.hazard;
  const maxAge = hazard.length - 1;
  const raw = hazard.map((value) => (value == null ? null : Math.max(0, value)));
  const values = [];
  for (let start = 0; start < raw.length; start += 5) {
    const window = raw.slice(start, start + 5).filter((item) => item != null);
    values.push(window.length ? window.reduce((sum, item) => sum + item, 0) / window.length : null);
  }
  const peak = Math.max(0.02, ...values.filter((value) => value != null));
  ctx.strokeStyle = scenario.id === 'danger' ? '#e8733b' : '#6e8f6a';
  ctx.lineWidth = 2;
  ctx.beginPath();
  let started = false;
  for (let bin = 0; bin < values.length; bin += 1) {
    const value = values[bin];
    if (value == null) continue;
    const age = bin * 5 + 2.5;
    const x = (age / maxAge) * w;
    const y = h - Math.min(1, value / peak) * (h - 6) - 3;
    if (!started) {
      ctx.moveTo(x, y);
      started = true;
    } else {
      ctx.lineTo(x, y);
    }
  }
  ctx.stroke();
  ctx.fillStyle = 'rgba(220,228,233,0.55)';
  ctx.font = '10px Arial';
  ctx.fillText('risk of death by age', 2, 11);
}

window.addEventListener('resize', () => {
  const w = window.innerWidth;
  const h = window.innerHeight;
  renderer.setSize(w, h);
  composer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  fxaa.uniforms.resolution.value.set(1 / w, 1 / h);
  fitChart();
});

fitChart();
window.DUR = DURATION;
window.seek = async (t) => {
  update(t);
};
update(0);
window.READY = true;
