import * as THREE from './three.module.js';

const W = window.innerWidth;
const H = window.innerHeight;
const BG = 0x2d3033;
const FPS = 30;

const renderer = new THREE.WebGLRenderer({antialias: true, preserveDrawingBuffer: true});
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.NoToneMapping;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(BG);
scene.fog = new THREE.Fog(BG, 38, 70);

const camera = new THREE.PerspectiveCamera(32, W / H, 0.1, 200);
const target = new THREE.Vector3(0, 0.3, 0);

scene.add(new THREE.HemisphereLight(0xdfe4e8, 0x2d3033, 1.7));
const key = new THREE.DirectionalLight(0xffffff, 2.2);
key.position.set(8, 16, -10);
scene.add(key);
const fill = new THREE.DirectionalLight(0xffffff, 0.6);
fill.position.set(-12, 8, 8);
scene.add(fill);

const data = await (await fetch('./simulation.json')).json();
const species = data.species.map((item) => new THREE.Color(item.hex));
const slate = new THREE.Color(0x3d4349);
const tileMix = new THREE.Color();

const tileGeometry = new THREE.CylinderGeometry(0.99, 0.99, 0.14, 6, 1);
tileGeometry.rotateY(Math.PI / 6);
const tileMaterial = new THREE.MeshStandardMaterial({roughness: 0.9, metalness: 0.0});
const tiles = new THREE.InstancedMesh(tileGeometry, tileMaterial, data.cells.length);
tiles.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(data.cells.length * 3), 3);
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
const bodyMaterial = new THREE.MeshStandardMaterial({roughness: 0.55, metalness: 0.0});
const bodies = new THREE.InstancedMesh(bodyGeometry, bodyMaterial, data.cells.length);
bodies.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(data.cells.length * 3), 3);
scene.add(bodies);

const eyeGeometry = new THREE.IcosahedronGeometry(0.048, 1);
const eyeMaterial = new THREE.MeshStandardMaterial({color: 0x0a0a0c, roughness: 0.35});
const eyes = new THREE.InstancedMesh(eyeGeometry, eyeMaterial, data.cells.length * 2);
scene.add(eyes);

const shadowGeometry = new THREE.CircleGeometry(0.34, 20);
shadowGeometry.rotateX(-Math.PI / 2);
const shadowMaterial = new THREE.MeshBasicMaterial({color: 0x16181a, transparent: true, opacity: 0.24, depthWrite: false});
const shadows = new THREE.InstancedMesh(shadowGeometry, shadowMaterial, data.cells.length);
scene.add(shadows);

const eyeLocal = [
  new THREE.Vector3(-0.095, 0.12, 0.30),
  new THREE.Vector3(0.095, 0.12, 0.30),
];
const eyeMatrix = new THREE.Matrix4();
const eyeQuat = new THREE.Quaternion();
const eyePos = new THREE.Vector3();
const eyeScale = new THREE.Vector3(1, 1, 1);

function updateCamera(t) {
  const u = Math.min(1, Math.max(0, t / 30));
  const angle = -1.15 + 0.30 * u;
  const radius = 21;
  camera.position.set(Math.cos(angle) * radius, 15.5, Math.sin(angle) * radius);
  camera.lookAt(target);
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
    dummy.position.set(cell.x, 0.36 + bob, -cell.y);
    const yaw = Math.atan2(camX - cell.x, camZ + cell.y);
    dummy.rotation.set(0, yaw, 0);
    dummy.scale.set(1, 1, 1);
    dummy.updateMatrix();
    bodies.setMatrixAt(index, dummy.matrix);
    bodies.setColorAt(index, species[kind]);
    tileMix.copy(slate).lerp(species[kind], 0.28);
    tiles.setColorAt(index, tileMix);
    dummy.position.set(cell.x, 0.152, -cell.y);
    dummy.rotation.set(0, 0, 0);
    dummy.updateMatrix();
    shadows.setMatrixAt(index, dummy.matrix);
    eyeQuat.setFromAxisAngle(new THREE.Vector3(0, 1, 0), yaw);
    for (let side = 0; side < 2; side += 1) {
      eyePos.copy(eyeLocal[side]).applyQuaternion(eyeQuat).add(new THREE.Vector3(cell.x, 0.36 + bob, -cell.y));
      eyeMatrix.compose(eyePos, eyeQuat, eyeScale);
      eyes.setMatrixAt(index * 2 + side, eyeMatrix);
    }
  }
  bodies.instanceMatrix.needsUpdate = true;
  bodies.instanceColor.needsUpdate = true;
  tiles.instanceColor.needsUpdate = true;
  shadows.instanceMatrix.needsUpdate = true;
  eyes.instanceMatrix.needsUpdate = true;
  updateCamera(t);
  renderer.render(scene, camera);
}

window.DUR = 30;
window.seek = async (t) => {
  update(t);
};
update(0);
window.READY = true;
