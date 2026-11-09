// Aging-evolution world: agent-based simulation + hazard overlay, pure f(t).
import * as THREE from './three.module.js';

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

// ground + grid
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(40, 26).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({color: 0x20262b, roughness: 1})
);
ground.position.set(0, -0.02, 0);
ground.receiveShadow = true;
scene.add(ground);

const grid = new THREE.GridHelper(24, 24, 0x3a4650, 0x2a3238);
grid.position.set(0, 0.0, 0);
grid.material.opacity = 0.35;
grid.material.transparent = true;
scene.add(grid);

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
const bodyGeo = new THREE.IcosahedronGeometry(0.26, 2);
bodyGeo.scale(1.0, 0.82, 1.05);
const bodyMat = new THREE.MeshStandardMaterial({roughness: 0.55, metalness: 0.0});
const MAX_AGENTS = 200;
const bodies = new THREE.InstancedMesh(bodyGeo, bodyMat, MAX_AGENTS);
bodies.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_AGENTS * 3), 3);
bodies.castShadow = true;
bodies.count = 0;
scene.add(bodies);

const maGeo = new THREE.IcosahedronGeometry(0.035, 1);
const maMat = new THREE.MeshStandardMaterial({color: 0x2a2d31, roughness: 0.4});
const maDots = new THREE.InstancedMesh(maGeo, maMat, MAX_AGENTS * 4);
maDots.count = 0;
scene.add(maDots);

const eyeGeo = new THREE.IcosahedronGeometry(0.045, 1);
const eyeMat = new THREE.MeshStandardMaterial({color: 0x0b0b0d, roughness: 0.3});
const eyes = new THREE.InstancedMesh(eyeGeo, eyeMat, MAX_AGENTS * 2);
eyes.count = 0;
scene.add(eyes);

const shadowGeo = new THREE.CircleGeometry(0.30, 18).rotateX(-Math.PI / 2);
const shadowMat = new THREE.MeshBasicMaterial({color: 0x101214, transparent: true, opacity: 0.22, depthWrite: false});
const blobs = new THREE.InstancedMesh(shadowGeo, shadowMat, MAX_AGENTS);
blobs.count = 0;
scene.add(blobs);

const dummy = new THREE.Object3D();
const eyeMatrix = new THREE.Matrix4();
const eyeQuat = new THREE.Quaternion();
const eyePos = new THREE.Vector3();
const eyeScale = new THREE.Vector3(1, 1, 1);
const eyeLocal = [new THREE.Vector3(-0.085, 0.10, 0.26), new THREE.Vector3(0.085, 0.10, 0.26)];

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
  const row = frames[index].agents;
  const rowNext = frames[next].agents;
  const camX = camera.position.x;
  const camZ = camera.position.z;

  let count = 0;
  let maCount = 0;
  const limit = Math.min(row.length, MAX_AGENTS);
  for (let i = 0; i < limit; i += 1) {
    const agent = row[i];
    const after = rowNext[i] || agent;
    if (!agent[3]) continue;
    const aliveNext = after[3] ? 1 : 0;
    const fade = aliveNext ? 1 : 1 - Math.min(1, mix * 1.6);
    if (fade <= 0.02) continue;
    const ax = agent[0] + (after[0] - agent[0]) * mix;
    const az = -(agent[1] + (after[1] - agent[1]) * mix);
    const age = agent[2];
    const scale = (0.82 + 0.011 * age) * fade;
    const yaw = Math.atan2(camX - ax, camZ - az);
    const bob = 0.03 * Math.sin(i * 0.7 + t * 2.4);

    dummy.position.set(ax, 0.28 + bob, az);
    dummy.rotation.set(0, yaw, 0);
    dummy.scale.set(scale, scale * 0.95, scale);
    dummy.updateMatrix();
    bodies.setMatrixAt(count, dummy.matrix);
    const colour = AGE_YOUNG.clone().lerp(AGE_OLD, Math.min(1, age / 80));
    bodies.setColorAt(count, colour);

    dummy.position.set(ax, 0.145, az);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(scale, 1, scale);
    dummy.updateMatrix();
    blobs.setMatrixAt(count, dummy.matrix);

    eyeQuat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
    for (let side = 0; side < 2; side += 1) {
      eyePos.copy(eyeLocal[side]).multiplyScalar(scale).applyQuaternion(eyeQuat);
      eyePos.add(new THREE.Vector3(ax, 0.28 + bob, az));
      eyeMatrix.compose(eyePos, eyeQuat, eyeScale);
      eyes.setMatrixAt(count * 2 + side, eyeMatrix);
    }

    const mutations = Math.min(4, agent[4]);
    for (let dot = 0; dot < mutations; dot += 1) {
      const angle = (dot / 4) * Math.PI * 2 + i * 0.6;
      const radius = 0.13 * scale;
      dummy.position.set(
        ax + Math.cos(angle) * radius,
        0.28 + bob + 0.24 * scale,
        az + Math.sin(angle) * radius
      );
      dummy.rotation.set(0, 0, 0);
      dummy.scale.set(1, 1, 1);
      dummy.updateMatrix();
      maDots.setMatrixAt(maCount, dummy.matrix);
      maCount += 1;
    }
    count += 1;
  }
  bodies.count = count;
  maDots.count = maCount;
  maDots.instanceMatrix.needsUpdate = true;
  eyes.count = count * 2;
  blobs.count = count;
  bodies.instanceMatrix.needsUpdate = true;
  bodies.instanceColor.needsUpdate = true;
  eyes.instanceMatrix.needsUpdate = true;
  blobs.instanceMatrix.needsUpdate = true;

  updateCamera(t);
  renderer.render(scene, camera);
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
  const alive = frame.agents.filter((agent) => agent[3]);
  const ma = alive.length ? alive.reduce((sum, agent) => sum + agent[4], 0) / alive.length : 0;
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
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  fitChart();
});

fitChart();
window.DUR = DURATION;
window.seek = async (t) => {
  update(t);
};
update(0);
window.READY = true;
