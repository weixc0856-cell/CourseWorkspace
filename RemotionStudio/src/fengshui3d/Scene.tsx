import React, {useMemo} from 'react';
import * as THREE from 'three';
import {useThree, useFrame} from '@react-three/fiber';
import {
  EffectComposer,
  Bloom,
  Noise,
  Vignette,
  DepthOfField,
  ChromaticAberration,
  SMAA,
  BrightnessContrast,
  HueSaturation,
} from '@react-three/postprocessing';
import {BlendFunction} from 'postprocessing';

export const W = 1080;
export const H = 1920;

export const GOLD = '#E0A45C';
export const JADE = '#2C4A45';
export const DEEP = '#08110F';
export const CYAN = '#8FD8D2';
export const WATER_Y = -0.6;

// ---------------------------------------------------------------- noise
const hash2 = (x: number, y: number) => {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453;
  return s - Math.floor(s);
};
const vnoise = (x: number, y: number) => {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const xf = x - xi;
  const yf = y - yi;
  const u = xf * xf * (3 - 2 * xf);
  const v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi);
  const b = hash2(xi + 1, yi);
  const c = hash2(xi, yi + 1);
  const d = hash2(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
};
const fbm = (x: number, y: number) =>
  0.5 * vnoise(x, y) + 0.25 * vnoise(x * 2.03, y * 2.03) + 0.125 * vnoise(x * 4.07, y * 4.07) + 0.0625 * vnoise(x * 8.11, y * 8.11);

// ---------------------------------------------------------------- terrain
export const heightAt = (x: number, z: number) => {
  let h = 15 * Math.exp(-(((x + 6) / 11) ** 2)) * (0.78 + 0.22 * Math.sin(z * 0.09 + 0.5));
  h += 3.2 * Math.sin(z * 0.21 + x * 0.08) * Math.exp(-(((x + 6) / 15) ** 2));
  h += 8 * Math.exp(-(((x + 34) ** 2 + (z - 16) ** 2) / 260));
  h += 6 * Math.exp(-(((x - 40) / 16) ** 2)) * (0.7 + 0.3 * Math.sin(z * 0.13 + 2));
  h += 2.2 * Math.sin(x * 0.24 + z * 0.19) * Math.exp(-(((x + 2) / 24) ** 2));
  h -= 3.6 * Math.exp(-(((x - 24) / 4.6) ** 2));
  h += 0.9 * Math.exp(-(((x - 24) / 12) ** 2));
  h += (fbm(x * 0.09 + 11, z * 0.09 + 5) - 0.5) * 2.6 * Math.exp(-(((x + 4) / 26) ** 2));
  h += (fbm(x * 0.33 + 3, z * 0.33 + 9) - 0.5) * 0.7;
  const r1 = 1 - Math.abs(2 * vnoise(x * 0.13 + 21, z * 0.13 + 7) - 1);
  h += r1 * r1 * 3.4 * Math.exp(-(((x + 6) / 28) ** 2));
  const r2 = 1 - Math.abs(2 * vnoise(x * 0.42 + 5, z * 0.42 + 13) - 1);
  h += r2 * r2 * 0.9;
  return h;
};

const TERRAIN_GLSL = `
float thash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float tnoise(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = thash(i), b = thash(i + vec2(1.0, 0.0));
  float c = thash(i + vec2(0.0, 1.0)), d = thash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float tfbm(vec2 p) {
  return 0.5 * tnoise(p) + 0.25 * tnoise(p * 2.03) + 0.125 * tnoise(p * 4.07) + 0.0625 * tnoise(p * 8.11);
}
float ridgeH(float x, float z) {
  float h = 15.0 * exp(-pow((x + 6.0) / 11.0, 2.0)) * (0.78 + 0.22 * sin(z * 0.09 + 0.5));
  h += 3.2 * sin(z * 0.21 + x * 0.08) * exp(-pow((x + 6.0) / 15.0, 2.0));
  h += 8.0 * exp(-(pow(x + 34.0, 2.0) + pow(z - 16.0, 2.0)) / 260.0);
  h += 6.0 * exp(-pow((x - 40.0) / 16.0, 2.0)) * (0.7 + 0.3 * sin(z * 0.13 + 2.0));
  h += 2.2 * sin(x * 0.24 + z * 0.19) * exp(-pow((x + 2.0) / 24.0, 2.0));
  h -= 3.6 * exp(-pow((x - 24.0) / 4.6, 2.0));
  h += 0.9 * exp(-pow((x - 24.0) / 12.0, 2.0));
  h += (tfbm(vec2(x * 0.09 + 11.0, z * 0.09 + 5.0)) - 0.5) * 2.6 * exp(-pow((x + 4.0) / 26.0, 2.0));
  h += (tfbm(vec2(x * 0.33 + 3.0, z * 0.33 + 9.0)) - 0.5) * 0.7;
  float r1 = 1.0 - abs(2.0 * tnoise(vec2(x * 0.13 + 21.0, z * 0.13 + 7.0)) - 1.0);
  h += r1 * r1 * 3.4 * exp(-pow((x + 6.0) / 28.0, 2.0));
  float r2 = 1.0 - abs(2.0 * tnoise(vec2(x * 0.42 + 5.0, z * 0.42 + 13.0)) - 1.0);
  h += r2 * r2 * 0.9;
  return h;
}
`;

const FOG_GLSL = `
uniform vec3 uFogColor;
uniform float uFogDensity;
float fogFactor(vec3 worldPos) {
  float d = length(worldPos - cameraPosition);
  return 1.0 - exp(-pow(uFogDensity * d, 2.0));
}
`;

const SUN = new THREE.Vector3(0.42, 0.34, -0.84).normalize();

// Baked shadow map: march the height field toward the sun and store the hit
// (the offline equivalent of what Lusion bakes in Houdini before shipping).
const SHADOW_N = 256;
const SHADOW_X0 = -80;
const SHADOW_X1 = 80;
const SHADOW_Z0 = -50;
const SHADOW_Z1 = 50;

const bakeShadow = () => {
  const data = new Uint8Array(SHADOW_N * SHADOW_N * 4);
  for (let j = 0; j < SHADOW_N; j += 1) {
    const z = SHADOW_Z0 + ((SHADOW_Z1 - SHADOW_Z0) * (j + 0.5)) / SHADOW_N;
    for (let i = 0; i < SHADOW_N; i += 1) {
      const x = SHADOW_X0 + ((SHADOW_X1 - SHADOW_X0) * (i + 0.5)) / SHADOW_N;
      const y0 = heightAt(x, z) + 0.25;
      let occ = 0;
      for (let k = 1; k <= 44; k += 1) {
        const t = k * 1.7;
        const px = x + SUN.x * t;
        const py = y0 + SUN.y * t;
        const pz = z + SUN.z * t;
        if (px < SHADOW_X0 || px > SHADOW_X1 || pz < SHADOW_Z0 || pz > SHADOW_Z1) break;
        if (heightAt(px, pz) > py + 0.05) {
          occ = 1;
          break;
        }
      }
      const v = occ ? 0 : 255;
      const o = (j * SHADOW_N + i) * 4;
      data[o] = v;
      data[o + 1] = v;
      data[o + 2] = v;
      data[o + 3] = 255;
    }
  }
  const tex = new THREE.DataTexture(data, SHADOW_N, SHADOW_N, THREE.RGBAFormat);
  tex.magFilter = THREE.LinearFilter;
  tex.minFilter = THREE.LinearFilter;
  tex.needsUpdate = true;
  return tex;
};

const SHADOW_TEX = bakeShadow();

const buildTerrainGeometry = (
  NX: number,
  NZ: number,
  X0: number,
  X1: number,
  Z0: number,
  Z1: number,
  sample: (x: number, z: number) => number
) => {
  const pos: number[] = [];
  const idx: number[] = [];
  for (let j = 0; j <= NZ; j += 1) {
    const z = Z0 + ((Z1 - Z0) * j) / NZ;
    for (let i = 0; i <= NX; i += 1) {
      const x = X0 + ((X1 - X0) * i) / NX;
      pos.push(x, sample(x, z), z);
    }
  }
  for (let j = 0; j < NZ; j += 1) {
    for (let i = 0; i < NX; i += 1) {
      const a = j * (NX + 1) + i;
      idx.push(a, a + NX + 1, a + 1, a + 1, a + NX + 1, a + NX + 2);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
};

const Terrain: React.FC = () => {
  const {geometry, material} = useMemo(() => {
    const g = buildTerrainGeometry(400, 320, -220, 220, -240, 120, heightAt);
    const m = new THREE.MeshStandardMaterial({color: 0x1b3330, roughness: 0.9, metalness: 0.08});
    m.onBeforeCompile = (shader) => {
      shader.uniforms.uGold = {value: new THREE.Color(GOLD)};
      shader.uniforms.uWater = {value: WATER_Y};
      shader.vertexShader = shader.vertexShader
        .replace('#include <common>', `#include <common>
varying float vH;
varying vec3 vWP;`)
        .replace('#include <begin_vertex>', `#include <begin_vertex>
vH = position.y;
vWP = (modelMatrix * vec4(position, 1.0)).xyz;`);
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', `#include <common>
varying float vH;
varying vec3 vWP;
uniform vec3 uGold;
uniform float uWater;
float th(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float tn(vec2 p) {
  vec2 i = floor(p); vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = th(i), b = th(i + vec2(1.0, 0.0));
  float c = th(i + vec2(0.0, 1.0)), d = th(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
float tfb(vec2 p) {
  return 0.5 * tn(p) + 0.25 * tn(p * 2.03) + 0.125 * tn(p * 4.07) + 0.0625 * tn(p * 8.11);
}`)
        .replace('#include <color_fragment>', `#include <color_fragment>
float upr = smoothstep(-3.0, 14.0, vH);
vec3 rock = mix(vec3(0.018, 0.038, 0.042), vec3(0.07, 0.13, 0.13), upr);
float grit = tfb(vWP.xz * 0.9);
rock *= 0.78 + 0.44 * grit;
float wet = smoothstep(uWater + 1.2, uWater - 0.2, vH);
rock = mix(rock, rock * 0.45 + vec3(0.01, 0.03, 0.03), wet);
diffuseColor.rgb = rock;`)
        .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
roughnessFactor = clamp(0.58 + 0.34 * tfb(vWP.xz * 1.7) - wet * 0.35, 0.12, 0.98);`)
        .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
{
  vec2 qa = vWP.xz * 0.9;
  vec2 qb = mat2(0.8, -0.6, 0.6, 0.8) * vWP.xz * 2.3;
  float e = 0.4;
  float a0 = tfb(qa), ax = tfb(qa + vec2(e, 0.0)), az = tfb(qa + vec2(0.0, e));
  float b0 = tfb(qb), bx = tfb(qb + vec2(e, 0.0)), bz = tfb(qb + vec2(0.0, e));
  vec3 nW = normalize(vec3(-((ax - a0) + (bx - b0) * 0.6) / e, 1.0, -((az - a0) + (bz - b0) * 0.6) / e));
  vec3 nV = normalize((viewMatrix * vec4(nW, 0.0)).xyz);
  normal = normalize(normal + nV * 0.22);
}`)
        .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
{
  float fh = vH / 1.7;
  float band = abs(fract(fh) - 0.5);
  float fw = fwidth(fh);
  float w = clamp(0.032 + fw * 0.5, 0.032, 0.085);
  float line = 1.0 - smoothstep(w * 0.7, w, band);
  line *= 1.0 - smoothstep(0.10, 0.32, fw);
  float hl = smoothstep(2.0, 13.0, vH);
  totalEmissiveRadiance += uGold * line * (0.3 + 0.95 * hl);
  float seam = 1.0 - smoothstep(0.0, 0.14, abs(vH - uWater));
  totalEmissiveRadiance += uGold * seam * 0.22;
}`);
    };
    m.customProgramCacheKey = () => 'terrain-pbr-v1';
    return {geometry: g, material: m};
  }, []);

  return <mesh geometry={geometry} material={material} castShadow receiveShadow />;
};

// mirrored terrain under the water line: planar reflection without an extra pass
const TerrainMirror: React.FC = () => {
  const {geometry, material} = useMemo(() => {
    const g = buildTerrainGeometry(200, 150, -220, 220, -240, 120, heightAt);
    const m = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        uFogColor: {value: new THREE.Color('#0b1719')},
        uFogDensity: {value: 0.0062},
        uGold: {value: new THREE.Color(GOLD)},
        uCyan: {value: new THREE.Color(CYAN)},
        uWater: {value: WATER_Y},
      },
      vertexShader: `
        varying vec3 vWorld;
        varying float vH;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorld = wp.xyz;
          vH = position.y;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform vec3 uFogColor;
        uniform float uFogDensity;
        uniform vec3 uGold;
        uniform vec3 uCyan;
        uniform float uWater;
        varying vec3 vWorld;
        varying float vH;
        void main() {
          float depth = clamp((uWater - vH) / 14.0, 0.0, 1.0);
          vec3 col = mix(uCyan * 0.16, vec3(0.02, 0.05, 0.055), depth);
          float fh = vH / 1.7;
          float band = abs(fract(fh) - 0.5);
          float w = clamp(fwidth(fh) * 1.1, 0.02, 0.12);
          float line = 1.0 - smoothstep(w * 0.6, w, band);
          col += uGold * line * 0.10;
          float f = fogFactor(vWorld);
          col = mix(col, uFogColor, 0.35 + f * 0.6);
          gl_FragColor = vec4(col, 0.42 * (1.0 - depth * 0.5));
        }
      `,
    });
    return {geometry: g, material: m};
  }, []);

  return <mesh geometry={geometry} material={material} position={[0, WATER_Y * 2, 0]} scale={[1, -1, 1]} renderOrder={1} />;
};

// ---------------------------------------------------------------- water
const Water: React.FC = () => {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        uniforms: {
          uTime: {value: 0},
          uFogColor: {value: new THREE.Color('#0b1719')},
          uFogDensity: {value: 0.0062},
          uGold: {value: new THREE.Color(GOLD)},
          uDeep: {value: new THREE.Color('#08110F')},
          uCyan: {value: new THREE.Color(CYAN)},
          uSun: {value: SUN.clone()},
        },
        vertexShader: `
          varying vec3 vWorld;
          void main() {
            vec4 wp = modelMatrix * vec4(position, 1.0);
            vWorld = wp.xyz;
            gl_Position = projectionMatrix * viewMatrix * wp;
          }
        `,
        fragmentShader: `
          uniform float uTime;
          uniform vec3 uGold;
          uniform vec3 uDeep;
          uniform vec3 uCyan;
          uniform vec3 uSun;
          varying vec3 vWorld;
          ${FOG_GLSL}
          void main() {
            vec2 p = vWorld.xz * 0.06;
            float w = sin(p.x * 3.1 + uTime * 0.9) * 0.5 + sin(p.y * 2.3 - uTime * 1.1) * 0.5
                    + sin((p.x + p.y) * 4.7 + uTime * 1.7) * 0.25
                    + sin((p.x - p.y) * 9.3 - uTime * 2.3) * 0.1;
            vec3 n = normalize(vec3(w * 0.14, 1.0, w * 0.18));
            vec3 viewDir = normalize(cameraPosition - vWorld);
            float fres = pow(1.0 - max(dot(n, viewDir), 0.0), 1.9);

            vec3 col = mix(uDeep, uCyan * 0.34, fres * 0.85);
            float spec = pow(max(dot(reflect(-uSun, n), viewDir), 0.0), 42.0);
            col += uGold * spec * 2.2;
            float glint = smoothstep(0.86, 1.0, sin(p.x * 6.1 + p.y * 4.3 + uTime * 1.9) * 0.5 + 0.5);
            col += uGold * glint * 0.05;

            float f = fogFactor(vWorld);
            col = mix(col, uFogColor, f * 0.9);
            gl_FragColor = vec4(col, mix(0.5, 0.93, fres));
          }
        `,
      }),
    []
  );

  useFrame(({clock}) => {
    material.uniforms.uTime.value = clock.getElapsedTime();
  });

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, WATER_Y, 0]} material={material} renderOrder={2}>
      <planeGeometry args={[220, 140, 1, 1]} />
    </mesh>
  );
};

// ---------------------------------------------------------------- particles
const COUNT = 45000;

const rand = (() => {
  let a = 0x9e3779b9;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
})();

const Particles: React.FC<{opacity: number}> = ({opacity}) => {
  const {geometry, material} = useMemo(() => {
    const seed = new Float32Array(COUNT * 4);
    for (let i = 0; i < COUNT; i += 1) {
      seed[i * 4 + 0] = rand();
      seed[i * 4 + 1] = (rand() - 0.5) * 96;
      seed[i * 4 + 2] = rand();
      seed[i * 4 + 3] = rand();
    }
    const seed2 = new Float32Array(COUNT * 2 * 4);
    const trail = new Float32Array(COUNT * 2);
    for (let i = 0; i < COUNT; i += 1) {
      for (let k = 0; k < 4; k += 1) {
        seed2[i * 8 + k] = seed[i * 4 + k];
        seed2[i * 8 + 4 + k] = seed[i * 4 + k];
      }
      trail[i * 2] = 0;
      trail[i * 2 + 1] = 1;
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(COUNT * 2 * 3), 3));
    g.setAttribute('aSeed', new THREE.BufferAttribute(seed2, 4));
    g.setAttribute('aTrail', new THREE.BufferAttribute(trail, 1));
    g.setDrawRange(0, COUNT * 2);

    const m = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: {value: 0},
        uOpacity: {value: 1},
        uGold: {value: new THREE.Color(GOLD)},
        uCyan: {value: new THREE.Color(CYAN)},
        uFogColor: {value: new THREE.Color('#0b1719')},
        uFogDensity: {value: 0.0062},
      },
      vertexShader: `
        attribute vec4 aSeed;
        attribute float aTrail;
        uniform float uTime;
        varying float vHot;
        varying float vAlpha;
        ${TERRAIN_GLSL}
        ${FOG_GLSL}
        vec3 curl(vec3 p, float t) {
          float n1 = tfbm(p.xz * 0.22 + vec2(t * 0.05, 0.0));
          float n2 = tfbm(p.xz * 0.22 + vec2(0.0, t * 0.05) + 17.0);
          float n3 = tfbm(p.xz * 0.22 + vec2(t * 0.05, t * 0.05) + 41.0);
          return vec3((n2 - 0.5), (n3 - 0.5) * 0.6, (n1 - 0.5)) * 3.6;
        }
        void main() {
          float span = 156.0;
          float x = mod(aSeed.x * span + uTime * 3.2 * (0.9 + aSeed.w * 0.45), span) - 78.0;
          float z = aSeed.y;
          float crest = exp(-pow((x + 6.0) / 15.0, 2.0));
          x += (aSeed.w - 0.5) * 2.0;
          x -= aTrail * (1.0 + crest * 2.6);
          float h = ridgeH(x, z);
          float lift = 0.5 + pow(aSeed.z, 1.7) * 5.4;
          vec3 swirl = curl(vec3(x, h, z), uTime + aSeed.x * 6.28);
          float y = h + lift + swirl.y * (0.8 + crest * 1.6);
          vec3 p = vec3(x + swirl.x * 0.6, y, z + swirl.z * 0.6);

          float submerged = smoothstep(${WATER_Y.toFixed(2)} + 1.4, ${WATER_Y.toFixed(2)}, y);
          vHot = clamp(crest * 1.1 - 0.12, 0.0, 1.0);
          vAlpha = (0.16 + 0.5 * aSeed.w * aSeed.w) * (1.0 - submerged * 0.92)
                 * smoothstep(9.0, 26.0, length(p - cameraPosition))
                 * (aTrail > 0.5 ? 0.45 : 1.0);

          vec4 mv = viewMatrix * modelMatrix * vec4(p, 1.0);
          float dist = length(p - cameraPosition);
          float sz = (1.0 + aSeed.w * 1.8 + crest * 1.5) * (132.0 / max(dist, 6.0));
          gl_PointSize = clamp(aTrail > 0.5 ? sz * 0.62 : sz, 1.0, 9.5);
          gl_Position = projectionMatrix * mv;
          vAlpha *= 1.0 - fogFactor(p) * 0.8;
        }
      `,
      fragmentShader: `
        uniform float uOpacity;
        uniform vec3 uGold;
        uniform vec3 uCyan;
        varying float vHot;
        varying float vAlpha;
        void main() {
          vec2 d = gl_PointCoord - 0.5;
          float r = length(d);
          if (r > 0.5) discard;
          float core = smoothstep(0.5, 0.0, r);
          vec3 col = mix(uCyan, uGold, vHot);
          gl_FragColor = vec4(col * (0.85 + core * 1.5), core * vAlpha * uOpacity);
        }
      `,
    });
    return {geometry: g, material: m};
  }, []);

  useFrame(({clock}) => {
    material.uniforms.uTime.value = clock.getElapsedTime();
    material.uniforms.uOpacity.value = opacity;
  });

  return <points geometry={geometry} material={material} frustumCulled={false} renderOrder={3} />;
};

// ---------------------------------------------------------------- far range
const FarRange: React.FC = () => {
  const {geometry, material} = useMemo(() => {
    const g = buildTerrainGeometry(120, 80, -260, 260, -320, -120, (x, z) => {
      const base = heightAt(x * 0.45 + 4, (z + 210) * 0.45);
      return base * 0.7 + 2.4 * Math.sin(x * 0.05 + z * 0.03);
    });
    const m = new THREE.ShaderMaterial({
      uniforms: {
        uFogColor: {value: new THREE.Color('#0b1719')},
        uFogDensity: {value: 0.0062},
        uGold: {value: new THREE.Color(GOLD)},
      },
      vertexShader: `
        varying vec3 vWorld;
        varying float vH;
        void main() {
          vec4 wp = modelMatrix * vec4(position, 1.0);
          vWorld = wp.xyz;
          vH = position.y;
          gl_Position = projectionMatrix * viewMatrix * wp;
        }
      `,
      fragmentShader: `
        uniform vec3 uGold;
        varying vec3 vWorld;
        varying float vH;
        ${FOG_GLSL}
        void main() {
          float fh = vH / 3.2;
          float band = abs(fract(fh) - 0.5);
          float w = clamp(fwidth(fh) * 0.9, 0.02, 0.1);
          float line = 1.0 - smoothstep(w * 0.6, w, band);
          vec3 col = vec3(0.040, 0.078, 0.082) + uGold * line * 0.14;
          float f = fogFactor(vWorld);
          col = mix(col, uFogColor, 0.42 + f * 0.56);
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });
    return {geometry: g, material: m};
  }, []);
  return <mesh geometry={geometry} material={material} frustumCulled={false} />;
};

// ---------------------------------------------------------------- sun disc
const sunTexture = (() => {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(255,238,205,1)');
  g.addColorStop(0.18, 'rgba(255,214,150,0.95)');
  g.addColorStop(0.45, 'rgba(224,164,92,0.35)');
  g.addColorStop(1, 'rgba(224,164,92,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
})();

const SunDisc = React.forwardRef<THREE.Mesh>((_, ref) => {
  const material = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        map: sunTexture,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        toneMapped: false,
      }),
    []
  );
  return (
    <mesh ref={ref} position={[SUN.x * 300, SUN.y * 300 + 30, SUN.z * 300]} material={material} frustumCulled={false}>
      <planeGeometry args={[150, 150]} />
    </mesh>
  );
});
SunDisc.displayName = 'SunDisc';

// ---------------------------------------------------------------- environment
const EnvLight: React.FC = () => {
  const {gl, scene} = useThree();
  React.useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const envScene = new THREE.Scene();
    const sky = new THREE.Mesh(
      new THREE.SphereGeometry(60, 32, 16),
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        uniforms: {uGold: {value: new THREE.Color(GOLD)}},
        vertexShader: 'varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
        fragmentShader: `
          uniform vec3 uGold;
          varying vec3 vP;
          void main() {
            float y = normalize(vP).y;
            vec3 top = vec3(0.02, 0.05, 0.055);
            vec3 mid = vec3(0.06, 0.11, 0.11);
            vec3 low = vec3(0.12, 0.10, 0.07);
            vec3 col = mix(low, mid, smoothstep(-0.2, 0.3, y));
            col = mix(col, top, smoothstep(0.3, 0.9, y));
            col += uGold * 0.25 * smoothstep(0.15, 0.0, abs(y - 0.16));
            gl_FragColor = vec4(col, 1.0);
          }
        `,
      })
    );
    envScene.add(sky);
    const rt = pmrem.fromScene(envScene, 0.04);
    scene.environment = rt.texture;
    return () => {
      scene.environment = null;
      rt.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
};

// ---------------------------------------------------------------- camera
type Key = {t: number; pos: [number, number, number]; look: [number, number, number]; fov: number};

const orbit = (aDeg: number, R: number, y: number): [number, number, number] => {
  const a = (aDeg * Math.PI) / 180;
  return [Math.cos(a) * R, y, Math.sin(a) * R];
};

const CAM_KEYS: Key[] = [
  {t: 0, pos: orbit(62, 150, 78), look: [0, 6, 0], fov: 32},
  {t: 14, pos: orbit(58, 145, 74), look: [-2, 7, 0], fov: 32},
  {t: 26, pos: orbit(52, 138, 70), look: [-4, 9, 0], fov: 34},
  {t: 34, pos: orbit(46, 132, 66), look: [-4, 9, 0], fov: 34},
  {t: 45, pos: orbit(38, 124, 60), look: [0, 8, 0], fov: 36},
  {t: 52, pos: orbit(30, 110, 40), look: [10, 2, 0], fov: 40},
  {t: 58, pos: orbit(22, 96, 32), look: [14, 1, 0], fov: 42},
  {t: 64, pos: orbit(16, 84, 26), look: [16, 0.5, 0], fov: 44},
  {t: 76, pos: orbit(12, 78, 24), look: [16, 0.5, 0], fov: 46},
  {t: 88, pos: orbit(20, 100, 44), look: [8, 4, 0], fov: 40},
  {t: 105, pos: orbit(34, 130, 64), look: [2, 6, 0], fov: 36},
  {t: 120, pos: orbit(50, 145, 74), look: [0, 6, 0], fov: 34},
  {t: 141, pos: orbit(58, 152, 80), look: [0, 5, 0], fov: 32},
  {t: 152, pos: orbit(62, 156, 82), look: [0, 5, 0], fov: 32},
];

const smoother = (x: number) => x * x * x * (x * (x * 6 - 15) + 10);

const camAt = (t: number) => {
  let i = 0;
  for (i = 0; i < CAM_KEYS.length - 1; i += 1) if (t <= CAM_KEYS[i + 1].t) break;
  const a = CAM_KEYS[Math.min(i, CAM_KEYS.length - 2)];
  const b = CAM_KEYS[Math.min(i + 1, CAM_KEYS.length - 1)];
  const p = smoother(Math.max(0, Math.min(1, (t - a.t) / Math.max(0.001, b.t - a.t))));
  const mix = (u: number[], v: number[]) => [u[0] + (v[0] - u[0]) * p, u[1] + (v[1] - u[1]) * p, u[2] + (v[2] - u[2]) * p];
  return {pos: mix(a.pos, b.pos), look: mix(a.look, b.look), fov: a.fov + (b.fov - a.fov) * p};
};

export const CameraRig: React.FC<{t: number; shake: number}> = ({t, shake}) => {
  const {camera} = useThree();
  const c = camAt(t);
  const jitter = Math.sin(t * 71.3) * 0.006 * shake;
  camera.position.set(c.pos[0] + jitter, c.pos[1] + jitter * 0.6, c.pos[2]);
  camera.lookAt(c.look[0], c.look[1], c.look[2]);
  const cam = camera as THREE.PerspectiveCamera;
  if (Math.abs(cam.fov - c.fov) > 0.01) {
    cam.fov = c.fov;
    cam.updateProjectionMatrix();
  }
  return null;
};

// ---------------------------------------------------------------- world
export const World: React.FC<{t: number; wind: number; shake: number; bloom: number}> = ({
  t,
  wind,
  shake,
  bloom,
}) => {
  const sunRef = React.useRef<THREE.Mesh>(null);
  const c = camAt(t);
  const focus = Math.min(
    0.85,
    Math.hypot(c.pos[0] - c.look[0], c.pos[1] - c.look[1], c.pos[2] - c.look[2]) / 420
  );
  return (
  <>
    <color attach="background" args={['#070f11']} />
    <fogExp2 attach="fog" args={['#0b1719', 0.0062]} />
    <CameraRig t={t} shake={shake} />
    <EnvLight />
    <directionalLight
      position={[SUN.x * 140, SUN.y * 140 + 20, SUN.z * 140]}
      intensity={3.6}
      color="#ffd7a0"
      castShadow
      shadow-mapSize-width={4096}
      shadow-mapSize-height={4096}
      shadow-camera-left={-160}
      shadow-camera-right={160}
      shadow-camera-top={160}
      shadow-camera-bottom={-160}
      shadow-camera-near={1}
      shadow-camera-far={420}
      shadow-bias={-0.0009}
    />
    <hemisphereLight args={['#356662', '#060d0e', 0.85]} />
    <ambientLight intensity={0.18} />
    <SunDisc ref={sunRef} />
    <Terrain />
    <TerrainMirror />
    <Water />
    <Particles opacity={wind} />
    <EffectComposer multisampling={0}>
      <Bloom intensity={bloom} luminanceThreshold={0.24} luminanceSmoothing={0.45} mipmapBlur radius={0.85} />
      <DepthOfField focusDistance={focus} focalLength={0.04} bokehScale={1.35} height={1080} />
      <ChromaticAberration offset={new THREE.Vector2(0.0006, 0.0009)} radialModulation={false} modulationOffset={0} />
      <HueSaturation saturation={0.06} hue={0} />
      <BrightnessContrast brightness={0.02} contrast={0.14} />
      <Noise opacity={0.028} blendFunction={BlendFunction.OVERLAY} />
      <Vignette eskil={false} offset={0.24} darkness={0.68} />
      <SMAA />
    </EffectComposer>
  </>
  );
};
