// WAYNE — environment concept frames (three variants x three shot sizes).
// Rendered as stills through capture.mjs with ?variant=...&shot=...
// These are art-direction probes, not production scenes.

import * as THREE from 'three';
import { EffectComposer } from './vendor/three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from './vendor/three/addons/postprocessing/RenderPass.js';
import { BokehPass } from './vendor/three/addons/postprocessing/BokehPass.js';
import { ShaderPass } from './vendor/three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from './vendor/three/addons/postprocessing/OutputPass.js';
import { VignetteShader } from './vendor/three/addons/shaders/VignetteShader.js';
import { FXAAShader } from './vendor/three/addons/shaders/FXAAShader.js';

const W = 1920, H = 1080;
const P = new URLSearchParams(location.search);
const VARIANT = P.get('variant') || 'atelier';
const SHOT = P.get('shot') || 'wide';

const COL = {
  wall: 0xF3F0E8, floor: 0xD8D1C5, graphite: 0x303236,
  orange: 0xE87532, paper: 0xFBFAF7, ceramic: 0xEFEAE0,
  stone: 0xE2DACB, wood: 0xC9AE8C,
};

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(COL.wall);
scene.fog = new THREE.Fog(COL.wall, 5.5, 14);
const camera = new THREE.PerspectiveCamera(36, W / H, 0.05, 40);

const mat = (color, rough = 0.85, metal = 0) =>
  new THREE.MeshStandardMaterial({ color, roughness: rough, metalness: metal });

const wallMat = mat(COL.wall, 0.96);
const floorMat = mat(COL.floor, 0.78);
const ceramicMat = mat(COL.ceramic, 0.5);
const stoneMat = mat(COL.stone, 0.7);
const graphiteMat = mat(COL.graphite, 0.4, 0.3);
const orangeMat = mat(COL.orange, 0.35);
const paperMat = mat(COL.paper, 0.8);
const woodMat = mat(COL.wood, 0.65);

// ---------------------------------------------------------------- light
scene.add(new THREE.HemisphereLight(0xffffff, 0xC9C1B2, 0.75));
const key = new THREE.DirectionalLight(0xfff4e6, 1.9);
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
const fill = new THREE.DirectionalLight(0xffffff, 0.35);
fill.position.set(0.5, 1.4, 3.2);
scene.add(fill);
rim.position.set(2.2, 1.8, -3.0);
scene.add(rim);

// ---------------------------------------------------------------- helpers
function box(size, pos, material, rot = [0, 0, 0]) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(...size), material);
  m.position.set(...pos);
  m.rotation.set(...rot);
  m.castShadow = m.receiveShadow = true;
  scene.add(m);
  return m;
}
function cyl(r, h, pos, material, rot = [0, 0, 0], segments = 48) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, segments), material);
  m.position.set(...pos);
  m.rotation.set(...rot);
  m.castShadow = m.receiveShadow = true;
  scene.add(m);
  return m;
}
function sheet(w, d, pos, rotY = 0) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, 0.0016, d), paperMat);
  m.position.set(...pos);
  m.rotation.y = rotY;
  m.castShadow = m.receiveShadow = true;
  scene.add(m);
  return m;
}

const floor = new THREE.Mesh(new THREE.PlaneGeometry(20, 20), floorMat);
floor.rotation.x = -Math.PI / 2;
floor.receiveShadow = true;
scene.add(floor);

// ---------------------------------------------------------------- variants
function buildAtelier() {
  // back wall with a tall opening, side wall: a real corner
  box([1.7, 2.4, 0.12], [-2.15, 1.2, -1.7], wallMat);
  box([1.7, 2.4, 0.12], [2.15, 1.2, -1.7], wallMat);
  box([2.6, 0.55, 0.12], [0, 2.12, -1.7], wallMat);
  box([0.12, 2.4, 3.4], [-2.45, 1.2, 0.0], wallMat);
  // recessed light behind the opening
  box([2.4, 2.2, 0.1], [0, 1.1, -2.6], mat(0xFAF7F0, 1.0));

  // stepped platform
  box([2.6, 0.10, 1.8], [0, 0.05, -0.15], stoneMat);
  box([1.7, 0.16, 1.1], [-0.15, 0.18, -0.25], ceramicMat);
  box([1.2, 0.08, 0.78], [0.05, 0.30, -0.30], ceramicMat);

  // work surface props
  sheet(0.34, 0.24, [0.12, 0.345, -0.24], 0.12);
  sheet(0.30, 0.21, [0.10, 0.348, -0.22], -0.25);
  cyl(0.035, 0.52, [-0.55, 0.26, -0.55], paperMat, [0, 0, 0.08]);
  cyl(0.028, 0.46, [-0.48, 0.23, -0.48], paperMat, [0, 0, -0.05]);
  cyl(0.024, 0.40, [-0.42, 0.20, -0.42], paperMat, [0, 0, 0.12]);
  box([0.30, 0.006, 0.03], [0.16, 0.352, -0.10], graphiteMat);
  // a small architectural model on the left plinth
  box([0.22, 0.16, 0.16], [-0.85, 0.26, -0.55], paperMat);
  box([0.10, 0.22, 0.10], [-0.78, 0.18, -0.50], paperMat);
  return { stage: 0.34, robot: [0.12, 0.34, -0.22] };
}

function buildStudio() {
  // curved cyclorama
  const wall = new THREE.Mesh(
    new THREE.CylinderGeometry(2.6, 2.6, 2.6, 96, 1, true, Math.PI * 0.6, Math.PI * 0.8),
    new THREE.MeshStandardMaterial({ color: COL.wall, roughness: 0.96, side: THREE.DoubleSide }),
  );
  wall.position.set(0, 1.3, -0.6);
  wall.receiveShadow = true;
  scene.add(wall);

  // stacked circular plinths
  cyl(1.05, 0.10, [0, 0.05, -0.25], stoneMat);
  cyl(0.70, 0.12, [0, 0.16, -0.25], ceramicMat);
  cyl(0.46, 0.22, [0, 0.33, -0.25], ceramicMat);

  // sculptural monolith with an orange slot
  box([0.62, 1.35, 0.30], [-1.15, 0.675, -1.05], ceramicMat);
  box([0.05, 0.95, 0.05], [-1.15, 0.62, -0.88], orangeMat);
  // a floating sheet
  const s = sheet(0.42, 0.30, [1.05, 0.9, -0.9], 0.35);
  s.rotation.x = -0.15;

  sheet(0.34, 0.24, [0.05, 0.445, -0.22], 0.18);
  cyl(0.03, 0.42, [0.30, 0.50, -0.30], paperMat, [0, 0, 0.1]);
  return { stage: 0.44, robot: [0.05, 0.44, -0.22] };
}

function buildBench() {
  // back wall + workbench
  box([6, 2.4, 0.12], [0, 1.2, -1.9], wallMat);
  box([0.12, 2.4, 3.6], [-2.6, 1.2, -0.1], wallMat);

  // bench top and legs
  box([2.0, 0.07, 0.80], [0, 0.72, -0.55], woodMat);
  [[-0.85, -0.85], [0.85, -0.85], [-0.85, -0.25], [0.85, -0.25]].forEach(([x, z]) => {
    cyl(0.045, 0.70, [x, 0.35, z], graphiteMat);
  });
  // tool rail
  box([1.7, 0.035, 0.035], [0, 1.18, -1.72], graphiteMat);
  [(-0.5), (0), (0.5)].forEach((x, i) => {
    cyl(0.012, 0.18, [x, 1.08, -1.70], i === 1 ? orangeMat : graphiteMat);
    box([0.05, 0.05, 0.02], [x, 1.00, -1.70], graphiteMat);
  });
  // task lamp
  cyl(0.05, 0.02, [0.78, 0.76, -0.82], graphiteMat);
  const arm = cyl(0.014, 0.55, [0.78, 1.02, -0.82], graphiteMat, [0.25, 0, 0]);
  cyl(0.095, 0.12, [0.64, 1.22, -0.58], graphiteMat, [0.45, 0, 0]);
  const spot = new THREE.SpotLight(0xffe9cf, 18, 3.2, 0.55, 0.6, 1.2);
  spot.position.set(0.66, 1.22, -0.62);
  spot.target.position.set(0.10, 0.76, -0.35);
  spot.castShadow = true;
  spot.shadow.mapSize.set(1024, 1024);
  scene.add(spot, spot.target);

  // props on the bench
  sheet(0.34, 0.24, [0.08, 0.762, -0.45], 0.10);
  sheet(0.30, 0.21, [0.06, 0.765, -0.42], -0.22);
  cyl(0.022, 0.16, [-0.42, 0.79, -0.55], graphiteMat, [0, 0, 1.57]);
  box([0.26, 0.006, 0.028], [0.38, 0.765, -0.40], graphiteMat);
  box([0.24, 0.03, 0.16], [-0.55, 0.79, -0.45], ceramicMat);
  return { stage: 0.76, robot: [0.06, 0.76, -0.40] };
}

const built = VARIANT === 'studio' ? buildStudio() : VARIANT === 'bench' ? buildBench() : buildAtelier();

// ---------------------------------------------------------------- character
const data = await fetch('./character.json').then(r => r.json());
const hero = new THREE.Group();
hero.scale.setScalar(0.55);
hero.position.set(...built.robot);
hero.rotation.y = VARIANT === 'bench' ? 0.5 : 0.35;
scene.add(hero);

const glow = (m) => { const c = m.clone(); c.vertexColors = true; return c; };
const matMap = {
  ceramic: glow(new THREE.MeshPhysicalMaterial({ color: COL.paper, roughness: 0.46, clearcoat: 0.08 })),
  warmgray: glow(new THREE.MeshStandardMaterial({ color: 0xC9C2B4, roughness: 0.6 })),
  graphite: glow(new THREE.MeshStandardMaterial({ color: 0x2A2E33, roughness: 0.4, metalness: 0.4 })),
  copper: glow(new THREE.MeshStandardMaterial({ color: 0xC97B4E, roughness: 0.3, metalness: 0.85 })),
  visor: glow(new THREE.MeshPhysicalMaterial({ color: 0x0B0E12, roughness: 0.14, metalness: 0.1, clearcoat: 1 })),
  eye: glow(new THREE.MeshStandardMaterial({ color: 0xFF6A2A, emissive: 0xFF5A1E, emissiveIntensity: 1.6, roughness: 0.3 })),
  orange: glow(new THREE.MeshStandardMaterial({ color: COL.orange, roughness: 0.4 })),
};
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
  mesh.castShadow = mesh.receiveShadow = true;
  const grp = groups[p.group];
  mesh.position.copy(new THREE.Vector3(...p.pivot)).sub(grp.pivot);
  grp.grp.add(mesh);
}

// ---------------------------------------------------------------- camera
const SHOTS = {
  atelier: {
    wide: [[2.5, 1.45, 2.9], [0.0, 0.62, -0.5]],
    medium: [[1.25, 0.95, 1.55], [0.10, 0.55, -0.25]],
    close: [[0.55, 0.72, 0.62], [0.14, 0.55, -0.18]],
  },
  studio: {
    wide: [[1.55, 1.25, 1.75], [0.0, 0.62, -0.35]],
    medium: [[1.05, 0.98, 1.15], [0.05, 0.58, -0.22]],
    close: [[0.52, 0.80, 0.55], [0.10, 0.58, -0.16]],
  },
  bench: {
    wide: [[2.8, 1.55, 2.6], [0.0, 0.85, -0.6]],
    medium: [[1.40, 1.10, 1.55], [0.05, 0.95, -0.40]],
    close: [[0.60, 0.95, 0.55], [0.10, 0.92, -0.32]],
  },
};
const [camPos, look] = SHOTS[VARIANT][SHOT];
camera.position.set(...camPos);
camera.lookAt(new THREE.Vector3(...look));

// ---------------------------------------------------------------- post
const composer = new EffectComposer(renderer);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));
const bokeh = new BokehPass(scene, camera, {
  focus: camera.position.distanceTo(new THREE.Vector3(...look)),
  aperture: SHOT === 'close' ? 0.0016 : 0.0008,
  maxblur: 0.008,
});
composer.addPass(bokeh);
const vignette = new ShaderPass(VignetteShader);
vignette.uniforms.offset.value = 0.96;
vignette.uniforms.darkness.value = 1.04;
composer.addPass(vignette);
composer.addPass(new OutputPass());
const fxaa = new ShaderPass(FXAAShader);
fxaa.material.uniforms.resolution.value.set(1 / W, 1 / H);
composer.addPass(fxaa);

window.DUR = 1;
window.seek = () => { composer.render(); };

document.fonts.ready.then(() => {
  composer.render();
  window.READY = true;
});
