import React, {useMemo} from 'react';
import * as THREE from 'three';
import {useThree} from '@react-three/fiber';
import {EffectComposer, Bloom} from '@react-three/postprocessing';
import {
  C,
  CUBE,
  DIMS,
  MAX_CUBES,
  REVEAL,
  REMOVE,
  RESTORE,
  SPACING,
  STAGE_TIMES,
  beatPulse,
  camDistance,
  clamp01,
  easeOut,
  isTopCube,
  lerp,
  lerp3,
  posAt,
  smooth,
  stageAt,
} from './timeline';

const BOX = new THREE.BoxGeometry(CUBE, CUBE, CUBE);
const EDGES = new THREE.EdgesGeometry(BOX);

type CubeState = {
  i: number;
  pos: [number, number, number];
  scale: number;
  top: boolean;
  solid: number;
  ghost: number;
};

function cubeStates(t: number): CubeState[] {
  const {k, p, isTransition} = stageAt(t);
  const count = 1 << k;
  const prev = k > 0 ? 1 << (k - 1) : 0;
  const reveal = smooth((t - REVEAL) / 2.2);
  const remove = smooth((t - REMOVE) / 2.2) * (1 - smooth((t - RESTORE) / 2.2));
  const lift = 0.5 * smooth((t - REVEAL) / 2.2) * (1 - smooth((t - (REMOVE - 4)) / 2.4));
  const states: CubeState[] = [];
  for (let i = 0; i < MAX_CUBES; i += 1) {
    if (i >= count) continue;
    let pos: [number, number, number];
    let scale = 1;
    if (isTransition && p < 1) {
      if (i < prev) {
        pos = lerp3(posAt(i, k - 1), posAt(i, k), p);
      } else {
        pos = lerp3(posAt(i - prev, k - 1), posAt(i, k), p);
        scale = 0.2 + 0.8 * easeOut(p);
      }
    } else {
      pos = posAt(i, k);
    }
    const top = k === 6 ? isTopCube(i) : false;
    if (top) {
      pos = [pos[0], pos[1] + lift, pos[2]];
    }
    const solid = top ? 1 - remove : 1;
    const ghost = top ? remove : 0;
    states.push({i, pos, scale: scale * (top ? solid : 1), top, solid, ghost});
    void reveal;
  }
  return states;
}

const CameraRig: React.FC<{t: number}> = ({t}) => {
  const {camera} = useThree();
  const r = camDistance(t);
  const angle = -0.55 + t * 0.045;
  const y = 5.1 + Math.sin(t * 0.32) * 0.55;
  const pulse = beatPulse(t, 8);
  const shake = Math.sin(t * 31.7) * 0.035 * pulse;
  camera.position.set(Math.sin(angle) * r + shake, y, Math.cos(angle) * r);
  camera.lookAt(0, 2.2, 0);
  let punch = 0;
  for (const st of STAGE_TIMES.slice(1)) {
    punch = Math.max(punch, Math.exp(-Math.pow((t - st) / 0.32, 2)));
  }
  const drop = Math.exp(-Math.pow((t - REVEAL) / 0.55, 2));
  camera.rotation.z += Math.sin(t * 29) * 0.008 * pulse;
  const persp = camera as THREE.PerspectiveCamera;
  persp.fov = 38 - 2.6 * punch - 4.5 * drop;
  persp.updateProjectionMatrix();
  return null;
};

const Cube: React.FC<{s: CubeState; t: number; reveal: number; pulse: number}> = ({
  s,
  t,
  reveal,
  pulse,
}) => {
  const revealed = t >= REVEAL;
  const topColor = s.top && revealed;
  const matColor = topColor ? '#0A0602' : '#041018';
  const emiColor = topColor ? C.amber : '#0E7A8C';
  const edgeColor = topColor ? C.amber : C.cyan;
  const shade = 0.86 + 0.28 * (((s.i * 7) % 13) / 12);
  const ei = (topColor ? 0.1 + 0.2 * reveal + 0.18 * pulse : 0.1 + 0.22 * pulse) * shade;
  return (
    <group position={s.pos} scale={s.scale}>
      <mesh geometry={BOX}>
        <meshStandardMaterial
          color={matColor}
          emissive={emiColor}
          emissiveIntensity={ei}
          metalness={0.9}
          roughness={0.18}
        />
      </mesh>
      <lineSegments geometry={EDGES}>
        <lineBasicMaterial
          color={edgeColor}
          transparent
          opacity={0.72 + 0.28 * pulse}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </lineSegments>
    </group>
  );
};

const GhostCube: React.FC<{s: CubeState; opacity: number}> = ({s, opacity}) => {
  if (opacity <= 0.01) return null;
  return (
    <lineSegments geometry={EDGES} position={s.pos} scale={1}>
      <lineBasicMaterial
        color={C.amber}
        transparent
        opacity={opacity}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </lineSegments>
  );
};

const Halo: React.FC<{t: number; pulse: number; k: number}> = ({t, pulse, k}) => {
  const r = 1.5 + 0.12 * k;
  return (
    <mesh position={[0, 0.3, 0]} rotation={[Math.PI / 2, 0, 0]} scale={1 + pulse * 0.02}>
      <torusGeometry args={[r, 0.006, 6, 180]} />
      <meshBasicMaterial
        color={C.cyan}
        transparent
        opacity={0.09}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
};

const Seam: React.FC<{t: number; pulse: number}> = ({t, pulse}) => {
  const a = smooth((t - REVEAL) / 1.4) * (1 - smooth((t - (REMOVE + 1)) / 1.4));
  const b = smooth((t - 133) / 1.5) * (1 - smooth((t - 150) / 1.5));
  const op = Math.max(a, b);
  if (op <= 0.01) return null;
  return (
    <mesh
      position={[0, 2.24, 0]}
      rotation={[Math.PI / 2, 0, 0]}
      scale={1 + pulse * 0.04}
    >
      <torusGeometry args={[1.09, 0.02, 8, 200]} />
      <meshBasicMaterial
        color={C.amber}
        transparent
        opacity={0.55 * op}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
};

const Shockwaves: React.FC<{t: number}> = ({t}) => {
  const times = [...STAGE_TIMES.slice(1), REVEAL, REMOVE, RESTORE];
  return (
    <group position={[0, 0.4, 0]}>
      {times.map((st, i) => {
        const age = t - st;
        if (age < 0 || age > 1.5) return null;
        const p = age / 1.5;
        const big = st === REVEAL;
        return (
          <mesh key={`${st}-${i}`} rotation={[Math.PI / 2, 0, 0]} scale={0.4 + p * (big ? 6 : 3.6)}>
            <torusGeometry args={[1, big ? 0.02 : 0.012, 6, 160]} />
            <meshBasicMaterial
              color={big ? C.amber : C.cyan}
              transparent
              opacity={(1 - p) * (big ? 0.7 : 0.45)}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </group>
  );
};

const Particles: React.FC<{t: number; pulse: number}> = ({t, pulse}) => {
  const N = 320;
  const positions = useMemo(() => {
    const arr = new Float32Array(N * 3);
    for (let i = 0; i < N; i += 1) {
      const seed = i * 1.371;
      const angle = seed + t * (0.06 + (i % 5) * 0.012);
      const radius = 2.8 + (i % 9) * 0.62 + pulse * 0.35;
      const y = 2.2 + Math.sin(seed * 2.1 + t * 0.55) * (1.4 + (i % 7) * 0.22);
      arr[i * 3] = Math.cos(angle) * radius;
      arr[i * 3 + 1] = y;
      arr[i * 3 + 2] = Math.sin(angle) * radius;
    }
    return arr;
  }, [t, pulse]);
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color={C.cyan}
        size={0.045}
        sizeAttenuation
        transparent
        opacity={0.7}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
};

const Stars: React.FC = () => {
  const positions = useMemo(() => {
    const N = 420;
    const arr = new Float32Array(N * 3);
    let s = 1234567;
    const rnd = () => {
      s = (s * 16807) % 2147483647;
      return s / 2147483647;
    };
    for (let i = 0; i < N; i += 1) {
      const a = rnd() * Math.PI * 2;
      const b = Math.acos(2 * rnd() - 1);
      const r = 18 + rnd() * 22;
      arr[i * 3] = Math.sin(b) * Math.cos(a) * r;
      arr[i * 3 + 1] = Math.cos(b) * r + 3;
      arr[i * 3 + 2] = Math.sin(b) * Math.sin(a) * r;
    }
    return arr;
  }, []);
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#8FC7D8"
        size={0.06}
        sizeAttenuation
        transparent
        opacity={0.55}
        depthWrite={false}
      />
    </points>
  );
};

const Core: React.FC<{pulse: number}> = ({pulse}) => (
  <group position={[0, 2.2, 0]}>
    <mesh scale={0.9 + pulse * 0.3}>
      <sphereGeometry args={[0.22, 16, 16]} />
      <meshBasicMaterial
        color={C.cyan}
        transparent
        opacity={0.38}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
    <pointLight intensity={14 + pulse * 30} distance={9} color={C.cyan} />
  </group>
);

export const Scene: React.FC<{t: number}> = ({t}) => {
  const {k} = stageAt(t);
  const pulse = beatPulse(t, 7);
  const reveal = smooth((t - REVEAL) / 2.2);
  const groupScaleBase = (() => {
    const {k: kk, p, isTransition} = stageAt(t);
    const base = [1.18, 1.04, 0.96, 0.88, 0.64, 0.58, 0.53][kk];
    if (!isTransition) return base;
    return lerp([1.18, 1.04, 0.96, 0.88, 0.64, 0.58, 0.53][Math.max(0, kk - 1)], base, p);
  })();
  const remove = smooth((t - REMOVE) / 2.2) * (1 - smooth((t - RESTORE) / 2.2));
  const groupScale = groupScaleBase * (1 + 0.028 * pulse) * (1 + 0.22 * remove);
  const groupY = 2.25 - 0.22 * remove;
  const rotY =
    0.4 +
    Math.min(t, 60) * 0.035 +
    Math.max(0, t - 60) * 0.012 +
    Math.max(0, t - 103) * 0.004 +
    Math.sin(t * 37) * 0.012 * pulse;
  const rotX = -0.1 + Math.sin(t * 0.27) * 0.05;
  const states = cubeStates(t);
  return (
    <>
      <CameraRig t={t} />
      <color attach="background" args={[C.bg]} />
      <fog attach="fog" args={[C.bg, 14, 36]} />

      <ambientLight intensity={0.35} />
      <directionalLight position={[8, 13, 7]} intensity={2.4} color="#D8F7FF" />
      <pointLight
        position={[Math.sin(t * 0.85) * 6, 4.0, Math.cos(t * 0.85) * 6]}
        intensity={38}
        distance={22}
        color={C.cyan}
      />
      <pointLight
        position={[Math.sin(t * 0.62 + 2) * 6, 2.6, Math.cos(t * 0.62 + 2) * 6]}
        intensity={16}
        distance={20}
        color={C.amber}
      />
      <spotLight position={[0, 13, 1]} angle={0.5} penumbra={0.9} intensity={65} distance={32} color={C.cyan} />
      <Core pulse={pulse} />

      <Stars />
      <Particles t={t} pulse={pulse} />

      <mesh position={[0, -0.45, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[70, 70]} />
        <meshStandardMaterial color="#040A0F" metalness={0.55} roughness={0.35} />
      </mesh>
      <gridHelper args={[40, 40, '#1A4A58', '#0B2530']} position={[0, -0.44, 0]} />

      <group position={[0, groupY, 0]} scale={groupScale} rotation={[rotX, rotY, 0]}>
        {states.map((s) => (
          <Cube key={s.i} s={s} t={t} reveal={reveal} pulse={pulse} />
        ))}
        {states
          .filter((s) => s.top && s.ghost > 0)
          .map((s) => (
            <GhostCube key={`g${s.i}`} s={s} opacity={0.2 * s.ghost} />
          ))}
      </group>

      <Halo t={t} pulse={pulse} k={k} />
      <Seam t={t} pulse={pulse} />
      <Shockwaves t={t} />

      <EffectComposer multisampling={0}>
        <Bloom intensity={0.65} luminanceThreshold={0.64} luminanceSmoothing={0.9} mipmapBlur />
      </EffectComposer>
    </>
  );
};
