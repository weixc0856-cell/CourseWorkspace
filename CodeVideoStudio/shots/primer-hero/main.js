// Primer-style hero world, v2: cinematic lighting, gradient dome, contact
// shadows, dust and a motivated camera dolly. Pure function of `t`.
import * as THREE from './three.module.js';

const W = window.innerWidth;
const H = window.innerHeight;
const FPS = 30;
const DURATION = 30;

const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.12;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x20262b, 0.016);

// --- gradient dome -----------------------------------------------------------
const domeGeometry = new THREE.SphereGeometry(90, 32, 16);
const domeTop = new THREE.Color(0x3c474f);
const domeBottom = new THREE.Color(0x14181b);
const domeColors = [];
const domePosition = domeGeometry.attributes.position;
for (let i = 0; i < domePosition.count; i += 1) {
  const v = Math.min(1, Math.max(0, (domePosition.getY(i) / 90 + 0.25) / 0.95));
  const colour = domeBottom.clone().lerp(domeTop, v);
  domeColors.push(colour.r, colour.g, colour.b);
}
domeGeometry.setAttribute('color', new THREE.Float32BufferAttribute(domeColors, 3));
const dome = new THREE.Mesh(
  domeGeometry,
  new THREE.MeshBasicMaterial({vertexColors: true, side: THREE.BackSide, depthWrite: false, fog: false})
);
scene.add(dome);

// --- ground ------------------------------------------------------------------
const ground = new THREE.Mesh(
  new THREE.CircleGeometry(46, 96).rotateX(-Math.PI / 2),
  new THREE.MeshStandardMaterial({color: 0x23282c, roughness: 1, metalness: 0})
);
ground.position.y = -0.012;
ground.receiveShadow = true;
scene.add(ground);

// --- lights ------------------------------------------------------------------
scene.add(new THREE.HemisphereLight(0xaabdcb, 0x181c1f, 1.0));

const key = new THREE.DirectionalLight(0xfff1df, 2.5);
key.position.set(9, 17, -7);
key.castShadow = true;
key.shadow.mapSize.set(2048, 2048);
key.shadow.camera.left = -13;
key.shadow.camera.right = 13;
key.shadow.camera.top = 13;
key.shadow.camera.bottom = -13;
key.shadow.camera.near = 1;
key.shadow.camera.far = 60;
key.shadow.bias = -0.0006;
key.shadow.normalBias = 0.02;
scene.add(key);

const rim = new THREE.DirectionalLight(0x7fb0c8, 1.0);
rim.position.set(-12, 9, 12);
scene.add(rim);

// --- camera ------------------------------------------------------------------
const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 220);
const lookAt = new THREE.Vector3(0, 0.4, 0);
const target = lookAt;

// vignette attached to the camera
function vignetteTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');
  const gradient = ctx.createRadialGradient(256, 256, 120, 256, 256, 256);
  gradient.addColorStop(0, 'rgba(0,0,0,0)');
  gradient.addColorStop(0.72, 'rgba(0,0,0,0.10)');
  gradient.addColorStop(1, 'rgba(0,0,0,0.55)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 512, 512);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
const vignette = new THREE.Mesh(
  new THREE.PlaneGeometry(2, 2),
  new THREE.MeshBasicMaterial({
    map: vignetteTexture(),
    transparent: true,
    depthTest: false,
    depthWrite: false,
    fog: false,
  })
);
vignette.position.set(0, 0, -1);
vignette.frustumCulled = false;
vignette.renderOrder = 999;
camera.add(vignette);
scene.add(camera);

// --- simulation data ---------------------------------------------------------
const data = await (await fetch('./simulation.json')).json();
const species = data.species.map((item) => new THREE.Color(item.hex));
const slate = new THREE.Color(0x3d4349);
const tileMix = new THREE.Color();

const tileGeometry = new THREE.CylinderGeometry(0.99, 0.99, 0.14, 6, 1);
tileGeometry.rotateY(Math.PI / 6);
const tileMaterial = new THREE.MeshStandardMaterial({roughness: 0.92, metalness: 0.0});
const tiles = new THREE.InstancedMesh(tileGeometry, tileMaterial, data.cells.length);
tiles.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(data.cells.length * 3), 3);
tiles.receiveShadow = true;
scene.add(tiles);

const dummy = new THREE.Object3D();
data.cells.forEach((cell, index) => {
  dummy.position.set(cell.x, 0.07, -cell.y);
  dummy.rotation.set(0, 0, 0);
  dummy.scale.set(1, 1, 1);
  dummy.updateMatrix();
  tiles.setMatrixAt(index, dummy.matrix);
  tiles.setColorAt(index, slate);
});
tiles.instanceMatrix.needsUpdate = true;

const bodyGeometry = new THREE.IcosahedronGeometry(0.30, 2);
bodyGeometry.scale(1.0, 0.86, 1.12);
const bodyMaterial = new THREE.MeshStandardMaterial({roughness: 0.5, metalness: 0.0});
const bodies = new THREE.InstancedMesh(bodyGeometry, bodyMaterial, data.cells.length);
bodies.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(data.cells.length * 3), 3);
bodies.castShadow = true;
scene.add(bodies);

const eyeGeometry = new THREE.IcosahedronGeometry(0.048, 1);
const eyeMaterial = new THREE.MeshStandardMaterial({color: 0x0a0a0c, roughness: 0.3});
const eyes = new THREE.InstancedMesh(eyeGeometry, eyeMaterial, data.cells.length * 2);
scene.add(eyes);

const contactGeometry = new THREE.CircleGeometry(0.36, 20);
contactGeometry.rotateX(-Math.PI / 2);
const contactMaterial = new THREE.MeshBasicMaterial({
  color: 0x121416,
  transparent: true,
  opacity: 0.20,
  depthWrite: false,
});
const contacts = new THREE.InstancedMesh(contactGeometry, contactMaterial, data.cells.length);
scene.add(contacts);

// --- dust --------------------------------------------------------------------
const dustCount = 320;
let dustSeed = 1337;
function rand() {
  dustSeed = (dustSeed * 1664525 + 1013904223) >>> 0;
  return dustSeed / 4294967296;
}
const dustPositions = new Float32Array(dustCount * 3);
for (let i = 0; i < dustCount; i += 1) {
  dustPositions[i * 3] = (rand() - 0.5) * 34;
  dustPositions[i * 3 + 1] = rand() * 7 + 0.4;
  dustPositions[i * 3 + 2] = (rand() - 0.5) * 34;
}
const dustGeometry = new THREE.BufferGeometry();
dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
const dust = new THREE.Points(
  dustGeometry,
  new THREE.PointsMaterial({
    color: 0xc7d2d9,
    size: 0.055,
    transparent: true,
    opacity: 0.36,
    depthWrite: false,
    sizeAttenuation: true,
    fog: false,
  })
);
scene.add(dust);

// --- animation ---------------------------------------------------------------
const eyeLocal = [new THREE.Vector3(-0.095, 0.12, 0.30), new THREE.Vector3(0.095, 0.12, 0.30)];
const eyeMatrix = new THREE.Matrix4();
const eyeQuat = new THREE.Quaternion();
const eyePos = new THREE.Vector3();
const eyeScale = new THREE.Vector3(1, 1, 1);

function smooth(x) {
  const v = Math.min(1, Math.max(0, x));
  return v * v * (3 - 2 * v);
}

function updateCamera(t) {
  const push = smooth(t / 20);
  const settle = smooth(Math.max(0, (t - 20) / 10));
  const angle = -1.35 + 1.15 * smooth(t / DURATION);
  const radius = 25.5 - 8.5 * push;
  const height = 17.5 - 5.5 * push + 1.5 * settle;
  camera.position.set(Math.cos(angle) * radius, height, Math.sin(angle) * radius);
  lookAt.set(0, 0.4 + 0.4 * push, 0);
  camera.lookAt(lookAt);
}

function update(t) {
  const frame = Math.min(data.frames - 1, Math.max(0, Math.round(t * FPS)));
  const row = data.frames_species[frame];
  const camX = camera.position.x;
  const camZ = camera.position.z;

  for (let index = 0; index < data.cells.length; index += 1) {
    const cell = data.cells[index];
    const kind = row[index];
    const bob = 0.035 * Math.sin(index * 0.7 + frame * 0.09);
    const breathe = 1 + 0.045 * Math.sin(index * 0.37 + frame * 0.10);
    const yaw = Math.atan2(camX - cell.x, camZ + cell.y);

    dummy.position.set(cell.x, 0.36 + bob, -cell.y);
    dummy.rotation.set(0, yaw, 0);
    dummy.scale.set(breathe, breathe * 0.98, breathe);
    dummy.updateMatrix();
    bodies.setMatrixAt(index, dummy.matrix);
    bodies.setColorAt(index, species[kind]);

    tileMix.copy(slate).lerp(species[kind], 0.30);
    tiles.setColorAt(index, tileMix);

    dummy.position.set(cell.x, 0.152, -cell.y);
    dummy.rotation.set(0, 0, 0);
    dummy.scale.set(1, 1, 1);
    dummy.updateMatrix();
    contacts.setMatrixAt(index, dummy.matrix);

    eyeQuat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
    for (let side = 0; side < 2; side += 1) {
      eyePos.copy(eyeLocal[side]).multiplyScalar(breathe).applyQuaternion(eyeQuat);
      eyePos.add(new THREE.Vector3(cell.x, 0.36 + bob, -cell.y));
      eyeMatrix.compose(eyePos, eyeQuat, eyeScale);
      eyes.setMatrixAt(index * 2 + side, eyeMatrix);
    }
  }

  bodies.instanceMatrix.needsUpdate = true;
  bodies.instanceColor.needsUpdate = true;
  tiles.instanceColor.needsUpdate = true;
  contacts.instanceMatrix.needsUpdate = true;
  eyes.instanceMatrix.needsUpdate = true;

  dust.rotation.y = t * 0.012;

  updateCamera(t);
  renderer.render(scene, camera);
}

window.DUR = DURATION;
window.seek = async (t) => {
  update(t);
};
update(0);
window.READY = true;
