import React, {useMemo, useRef} from 'react';
import * as THREE from 'three';
import {useFrame, useLoader, useThree} from '@react-three/fiber';
import {staticFile} from 'remotion';
import {GLTFLoader} from 'three/examples/jsm/loaders/GLTFLoader.js';
import {EffectComposer, Bloom, Vignette, Noise, SMAA} from '@react-three/postprocessing';
import {BlendFunction} from 'postprocessing';
// @ts-ignore - example module without bundled types
import {RoomEnvironment} from 'three/examples/jsm/environments/RoomEnvironment.js';

const ORANGE = '#E8733B';
const CYAN = '#7AD8E8';
const BLUE = '#2E6FA3';
const DEEP = '#173A5C';
const INK = '#07090D';

// ------------------------------------------------------------------ camera
type CamKey = {t: number; pos: [number, number, number]; look: [number, number, number]};
const CAM: CamKey[] = [
  {t: 0, pos: [7.8, 3.2, 8.8], look: [0, 0.78, 0]},
  {t: 4, pos: [6.0, 2.4, 9.0], look: [0, 0.78, 0]},
  {t: 8, pos: [2.0, 1.8, 9.4], look: [0, 0.78, 0]},
  {t: 12, pos: [-1.0, 1.1, 8.4], look: [0, 0.55, 0]},
  {t: 16, pos: [-5.0, 1.8, 7.4], look: [-0.6, 0.78, 0]},
  {t: 21, pos: [-7.6, 2.4, 6.4], look: [-1.4, 0.8, 0]},
  {t: 26, pos: [-8.6, 2.8, 7.6], look: [0, 0.8, 0]},
  {t: 30, pos: [-9.6, 3.0, 8.4], look: [0, 0.82, 0]},
];

const smooth = (x: number) => {
  const c = Math.max(0, Math.min(1, x));
  return c * c * (3 - 2 * c);
};

const CameraRig: React.FC<{t: number}> = ({t}) => {
  const {camera} = useThree();
  const c = useMemo(() => {
    let i = 0;
    while (i < CAM.length - 2 && t > CAM[i + 1].t) i += 1;
    const a = CAM[i];
    const b = CAM[i + 1];
    const p = smooth((t - a.t) / Math.max(0.001, b.t - a.t));
    const pos = new THREE.Vector3(...a.pos).lerp(new THREE.Vector3(...b.pos), p);
    const look = new THREE.Vector3(...a.look).lerp(new THREE.Vector3(...b.look), p);
    pos.x += Math.sin(t * 0.55) * 0.03;
    pos.y += Math.sin(t * 0.42 + 1.2) * 0.022;
    look.x += Math.sin(t * 0.37 + 0.4) * 0.018;
    return {pos, look};
  }, [t]);
  camera.position.copy(c.pos);
  camera.lookAt(c.look);
  return null;
};

// ------------------------------------------------------------------ studio
const Studio: React.FC = () => {
  const {gl, scene} = useThree();
  useMemo(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    return scene.environment;
  }, [gl, scene]);
  return null;
};

// ------------------------------------------------------------------ car
const Body: React.FC = () => {
  const bodyGeo = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(2.05, 0.3);
    s.lineTo(2.05, 0.52);
    s.bezierCurveTo(2.03, 0.72, 1.85, 0.82, 1.5, 0.86);
    s.bezierCurveTo(1.15, 0.9, 0.92, 1.0, 0.62, 1.2);
    s.bezierCurveTo(0.45, 1.33, 0.15, 1.38, -0.2, 1.38);
    s.bezierCurveTo(-0.75, 1.32, -1.35, 1.08, -1.9, 0.86);
    s.lineTo(-2.05, 0.72);
    s.lineTo(-2.05, 0.3);
    s.closePath();
    const g = new THREE.ExtrudeGeometry(s, {
      depth: 1.66,
      bevelEnabled: true,
      bevelThickness: 0.055,
      bevelSize: 0.055,
      bevelSegments: 3,
      curveSegments: 32,
      steps: 1,
    });
    g.translate(0, 0, -0.83);
    g.computeVertexNormals();
    return g;
  }, []);

  const windowShape = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(0.72, 0.98);
    s.bezierCurveTo(0.56, 1.18, 0.28, 1.28, 0.0, 1.3);
    s.bezierCurveTo(-0.42, 1.32, -0.78, 1.22, -1.05, 1.03);
    s.lineTo(-0.9, 0.98);
    s.bezierCurveTo(-0.6, 1.15, -0.25, 1.2, 0.05, 1.17);
    s.bezierCurveTo(0.36, 1.14, 0.56, 1.02, 0.66, 0.98);
    s.closePath();
    return s;
  }, []);

  const windowGeo = useMemo(
    () => new THREE.ExtrudeGeometry(windowShape, {depth: 0.014, bevelEnabled: false, curveSegments: 24, steps: 1}),
    [windowShape],
  );

  const trimGeo = useMemo(() => {
    const pts = windowShape.getPoints(72).map((p) => new THREE.Vector3(p.x, p.y, 0));
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, [windowShape]);

  const pressureGeo = useMemo(() => {
    const g = bodyGeo.clone();
    const pos = g.getAttribute('position') as THREE.BufferAttribute;
    const colors: number[] = [];
    const c = new THREE.Color();
    const base = new THREE.Color('#000000');
    const hot = new THREE.Color(ORANGE);
    const low = new THREE.Color(CYAN);
    for (let i = 0; i < pos.count; i += 1) {
      const x = pos.getX(i);
      c.copy(base);
      const h = Math.max(0, Math.min(1, (x - 1.9) / 0.32));
      if (h > 0) c.lerp(hot, h * 0.95);
      const l = Math.max(0, Math.min(1, (-x - 1.8) / 0.5));
      if (l > 0) c.lerp(low, l * 0.75);
      colors.push(c.r, c.g, c.b);
    }
    g.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
    return g;
  }, [bodyGeo]);

  const wheel = (x: number, z: number) => {
    const side = Math.sign(z) || 1;
    return (
      <group key={`${x}-${z}`} position={[x, 0.34, z]}>
        <mesh rotation={[Math.PI / 2, 0, 0]} castShadow>
          <cylinderGeometry args={[0.34, 0.34, 0.25, 40]} />
          <meshStandardMaterial color="#05060A" roughness={0.94} metalness={0.04} />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <cylinderGeometry args={[0.225, 0.225, 0.27, 36]} />
          <meshStandardMaterial color="#9FABB8" roughness={0.3} metalness={0.95} />
        </mesh>
        <mesh position={[0, 0, side * 0.137]}>
          <torusGeometry args={[0.225, 0.012, 8, 40]} />
          <meshStandardMaterial color="#DCE4EC" roughness={0.18} metalness={1} />
        </mesh>
        {Array.from({length: 5}).map((_, i) => {
          const a = (i / 5) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 0.11, Math.sin(a) * 0.11, side * 0.138]} rotation={[0, 0, a]}>
              <boxGeometry args={[0.03, 0.19, 0.014]} />
              <meshStandardMaterial color="#C7D1DC" roughness={0.22} metalness={1} />
            </mesh>
          );
        })}
        <mesh position={[0, 0, side * 0.14]}>
          <cylinderGeometry args={[0.055, 0.055, 0.015, 24]} />
          <meshStandardMaterial color="#E8733B" roughness={0.3} metalness={0.8} />
        </mesh>
      </group>
    );
  };

  return (
    <group>
      <mesh geometry={bodyGeo} castShadow receiveShadow>
        <meshPhysicalMaterial
          color="#303B49"
          roughness={0.42}
          metalness={0.25}
          clearcoat={0.25}
          clearcoatRoughness={0.3}
          envMapIntensity={0.95}
        />
      </mesh>

      {[0.848, -0.85].map((z) => (
        <mesh key={z} geometry={windowGeo} position={[0, 0, z]}>
          <meshPhysicalMaterial
            color="#0A1018"
            roughness={0.06}
            metalness={0.55}
            transparent
            opacity={0.94}
            envMapIntensity={2.1}
          />
        </mesh>
      ))}
      {[0.862, -0.864].map((z) => (
        <lineLoop key={`trim-${z}`} geometry={trimGeo} position={[0, 0, z]}>
          <lineBasicMaterial color="#B7C6D6" transparent opacity={0.55} toneMapped={false} />
        </lineLoop>
      ))}

      {[1.4, -1.4].map((x) => (
        <React.Fragment key={x}>
          {[0.86, -0.86].map((z) => wheel(x, z))}
        </React.Fragment>
      ))}

      {/* front face: grille, headlights, splitter */}
      <mesh position={[2.205, 0.45, 0]}>
        <boxGeometry args={[0.03, 0.17, 1.02]} />
        <meshStandardMaterial color="#050609" roughness={0.55} metalness={0.7} />
      </mesh>
      {[0.5, -0.5].map((z) => (
        <mesh key={`head-${z}`} position={[2.2, 0.69, z]}>
          <boxGeometry args={[0.025, 0.07, 0.26]} />
          <meshBasicMaterial color="#D6EDF7" toneMapped={false} />
        </mesh>
      ))}
      <mesh position={[2.06, 0.19, 0]}>
        <boxGeometry args={[0.24, 0.025, 1.62]} />
        <meshStandardMaterial color="#050609" roughness={0.4} metalness={0.7} />
      </mesh>

      {/* rear: light bar, diffuser */}
      <mesh position={[-2.05, 0.18, 0]}>
        <boxGeometry args={[0.22, 0.025, 1.5]} />
        <meshStandardMaterial color="#050609" roughness={0.4} metalness={0.7} />
      </mesh>

      {/* rocker accents */}
      {[0.845, -0.847].map((z) => (
        <mesh key={`accent-${z}`} position={[0, 0.3, z]}>
          <boxGeometry args={[3.05, 0.012, 0.01]} />
          <meshBasicMaterial color={ORANGE} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
};

// ------------------------------------------------------------------ flow
type Lane = {
  pts: [number, number, number][];
  n: number;
  spread: number;
  opacity: number;
  base: string;
  hot?: number;
  fade?: boolean;
};

const LANES: Lane[] = [
  {
    pts: [[7, 1.15, 0], [4, 1.18, 0], [2.2, 1.35, 0], [0.8, 1.55, 0], [-0.2, 1.6, 0], [-1.2, 1.4, 0], [-2.2, 1.18, 0], [-4.6, 1.05, 0], [-9, 0.95, 0]],
    n: 30, spread: 0.46, opacity: 0.4, base: CYAN, hot: 0.5,
  },
  {
    pts: [[7, 0.98, 1.0], [4, 0.98, 1.05], [2, 1.05, 1.05], [0.2, 1.12, 1.03], [-1.2, 1.02, 1.0], [-2.4, 0.92, 0.96], [-9, 0.82, 0.92]],
    n: 18, spread: 0.075, opacity: 0.36, base: CYAN,
  },
  {
    pts: [[7, 0.62, 1.12], [4, 0.62, 1.18], [2, 0.68, 1.18], [0.2, 0.72, 1.16], [-1.2, 0.7, 1.1], [-2.4, 0.66, 1.04], [-9, 0.6, 1.0]],
    n: 16, spread: 0.07, opacity: 0.3, base: BLUE,
  },
  {
    pts: [[7, 0.18, 0.45], [4, 0.16, 0.5], [2, 0.15, 0.52], [0, 0.15, 0.52], [-1.5, 0.18, 0.55], [-3, 0.25, 0.68], [-5.5, 0.32, 0.82]],
    n: 16, spread: 0.1, opacity: 0.26, base: BLUE, fade: true,
  },
  {
    pts: [[7, 0.38, 0.92], [4, 0.38, 0.92], [2.2, 0.36, 0.92], [1.4, 0.34, 0.9], [0.6, 0.34, 0.9], [-0.2, 0.42, 0.9], [-1.2, 0.46, 0.92], [-2.4, 0.5, 0.96], [-4.8, 0.42, 1.0]],
    n: 12, spread: 0.06, opacity: 0.3, base: CYAN, hot: 0.7, fade: true,
  },

];

const buildLines = (): {line: THREE.Line; curve: THREE.CatmullRomCurve3}[] => {
  const out: {line: THREE.Line; curve: THREE.CatmullRomCurve3}[] = [];
  LANES.forEach((lane, li) => {
    const mirrorless = lane.pts.every((p) => p[2] === 0);
    for (let k = 0; k < lane.n; k += 1) {
      for (const mirror of [1, -1]) {
        if (mirrorless && mirror === -1) continue;
        const zoff = lane.spread * (lane.n === 1 ? 0 : (k / (lane.n - 1)) * 2 - 1);
        const phase = k * 1.37 + li * 2.11;
        const pts = lane.pts.map((p, i) => {
          const w = i === 0 || i === lane.pts.length - 1 ? 0.35 : 1;
          return new THREE.Vector3(
            p[0] + Math.sin(phase + i * 0.7) * 0.015,
            p[1] + Math.sin(phase * 0.7 + i * 0.9) * 0.02 * w,
            (p[2] + zoff + Math.sin(phase * 1.3 + i * 0.6) * 0.012) * mirror,
          );
        });
        const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
        const samples = curve.getPoints(110);
        const geo = new THREE.BufferGeometry().setFromPoints(samples);
        const colors: number[] = [];
        const c = new THREE.Color();
        const warm = new THREE.Color(ORANGE);
        const cool = new THREE.Color(lane.base);
        const deep = new THREE.Color(DEEP);
        samples.forEach((p) => {
          c.copy(cool);
          const hot = Math.max(0, Math.min(1, (p.x - 1.5) / 1.3)) * (lane.hot ?? 0.25);
          if (hot > 0) c.lerp(warm, hot);
          const wake = Math.max(0, Math.min(1, (-p.x - 2.0) / 4));
          if (wake > 0 && lane.base !== DEEP) c.lerp(deep, wake * 0.65);
          if (lane.fade && p.x < -2.4) c.multiplyScalar(Math.max(0, 1 - (-p.x - 2.4) / 2.2));
          colors.push(c.r, c.g, c.b);
        });
        geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        const mat = new THREE.LineBasicMaterial({
          vertexColors: true,
          transparent: true,
          opacity: lane.opacity * (0.7 + 0.3 * (k / Math.max(1, lane.n - 1))),
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        });
        out.push({line: new THREE.Line(geo, mat), curve});
      }
    }
  });
  return out;
};

const FlowLines: React.FC = () => {
  const items = useMemo(buildLines, []);
  return (
    <group>
      {items.map((it, i) => (
        <primitive key={i} object={it.line} />
      ))}
    </group>
  );
};

const Particles: React.FC<{t: number}> = ({t}) => {
  const tRef = useRef(t);
  tRef.current = t;
  const data = useMemo(() => {
    const items = buildLines();
    return Array.from({length: 360}, (_, i) => {
      const it = items[Math.floor((i * 7.31) % items.length)];
      return {
        curve: it.curve,
        offset: ((i * 0.61803398875) % 1 + 1) % 1,
        speed: 0.08 + ((i * 5) % 13) / 110,
        jitter: ((i * 31) % 17) / 17 - 0.5,
      };
    });
  }, []);
  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(data.length * 3), 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(new Float32Array(data.length * 3), 3));
    return g;
  }, [data.length]);
  const points = useMemo(() => {
    const mat = new THREE.PointsMaterial({
      size: 0.026,
      vertexColors: true,
      transparent: true,
      opacity: 0.9,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      sizeAttenuation: true,
    });
    return new THREE.Points(geo, mat);
  }, [geo]);

  useFrame(() => {
    const tt = tRef.current;
    const pos = geo.getAttribute('position') as THREE.BufferAttribute;
    const col = geo.getAttribute('color') as THREE.BufferAttribute;
    const c = new THREE.Color();
    data.forEach((d, i) => {
      const u = (d.offset + tt * d.speed) % 1;
      const p = d.curve.getPoint(u);
      pos.setXYZ(i, p.x + d.jitter * 0.03, p.y + d.jitter * 0.02, p.z + d.jitter * 0.03);
      c.copy(new THREE.Color(CYAN));
      const hot = Math.max(0, Math.min(1, (p.x - 1.5) / 1.3));
      if (hot > 0) c.lerp(new THREE.Color(ORANGE), hot * 0.8);
      col.setXYZ(i, c.r, c.g, c.b);
    });
    pos.needsUpdate = true;
    col.needsUpdate = true;
  });

  return <primitive object={points} />;
};

const Vortex: React.FC<{t: number; z: number; dir: number}> = ({t, z, dir}) => {
  const ref = useRef<THREE.Group>(null);
  const geo = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    for (let i = 0; i <= 100; i += 1) {
      const x = -2.1 - i * 0.075;
      const a = i * 0.3;
      const r = 0.08 + i * 0.0035;
      pts.push(new THREE.Vector3(x, 0.78 + r * Math.sin(a), z + r * Math.cos(a)));
    }
    const curve = new THREE.CatmullRomCurve3(pts, false, 'centripetal');
    return new THREE.TubeGeometry(curve, 130, 0.02, 7, false);
  }, [z]);
  useFrame(() => {
    if (ref.current) ref.current.rotation.x = t * 0.9 * dir;
  });
  return (
    <group ref={ref}>
      <mesh geometry={geo}>
        <meshBasicMaterial color={CYAN} transparent opacity={0.55 * smooth((t - 12) / 4)} blending={THREE.AdditiveBlending} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
};

// ------------------------------------------------------------------ scene
const Backdrop: React.FC = () => (
  <mesh scale={70}>
    <sphereGeometry args={[1, 32, 24]} />
    <shaderMaterial
      side={THREE.BackSide}
      depthWrite={false}
      uniforms={{
        top: {value: new THREE.Color('#101A26')},
        bottom: {value: new THREE.Color('#04060A')},
      }}
      vertexShader={`varying vec3 vP; void main(){ vP = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`}
      fragmentShader={`varying vec3 vP; uniform vec3 top; uniform vec3 bottom; void main(){ float h = normalize(vP).y * 0.5 + 0.5; vec3 c = mix(bottom, top, smoothstep(0.18, 0.88, h)); gl_FragColor = vec4(c, 1.0); }`}
    />
  </mesh>
);

const Shadow: React.FC = () => {
  const tex = useMemo(() => {
    const c = document.createElement('canvas');
    c.width = 256;
    c.height = 256;
    const ctx = c.getContext('2d')!;
    const g = ctx.createRadialGradient(128, 128, 8, 128, 128, 124);
    g.addColorStop(0, 'rgba(0,0,0,0.92)');
    g.addColorStop(0.55, 'rgba(0,0,0,0.45)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 256, 256);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, []);
  return (
    <mesh position={[0, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[6.6, 3.4]} />
      <meshBasicMaterial map={tex} transparent opacity={0.92} depthWrite={false} />
    </mesh>
  );
};

const DrivAerModel: React.FC = () => {
  const gltf = useLoader(GLTFLoader, staticFile('staging/t1-01-why-aerodynamics/drivaer.glb'));
  const model = useMemo(() => gltf.scene.clone(true), [gltf.scene]);
  return <primitive object={model} rotation={[0, Math.PI, 0]} />;
};

export const World: React.FC<{t: number; car?: 'drivaer' | 'procedural'}> = ({t, car = 'drivaer'}) => (
  <>
    <Studio />
    <CameraRig t={t} />
    <Backdrop />
    <fogExp2 attach="fog" args={['#06090D', 0.026]} />

    <ambientLight intensity={0.22} />
    <spotLight
      position={[6, 7.2, 2.5]}
      angle={0.55}
      penumbra={1}
      intensity={82}
      color="#FFF1DF"
      castShadow
      shadow-mapSize-width={1024}
      shadow-mapSize-height={1024}
    />
    <pointLight position={[-5, 2.8, -4]} intensity={70} color={CYAN} distance={24} />
    <pointLight position={[2.0, 1.8, -6]} intensity={30} color={ORANGE} distance={18} />
    <pointLight position={[0, 3.0, 6.5]} intensity={14} color="#93A9C4" distance={22} />
    <pointLight position={[2.45, 0.55, 0]} intensity={3} color={ORANGE} distance={1.6} />

    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]} receiveShadow>
      <planeGeometry args={[90, 90]} />
      <meshStandardMaterial color="#07090D" roughness={0.56} metalness={0.16} envMapIntensity={0.28} />
    </mesh>
    <Shadow />

    {car === 'drivaer' ? <DrivAerModel /> : <Body />}

    <FlowLines />
    <Particles t={t} />

    <mesh position={[-5.8, 0.88, 0]} rotation={[0, 0, Math.PI / 2]}>
      <cylinderGeometry args={[0.45, 1.4, 6.6, 36, 1, true]} />
      <meshBasicMaterial color="#1E4E7A" transparent opacity={0.035} side={THREE.DoubleSide} blending={THREE.AdditiveBlending} depthWrite={false} />
    </mesh>

    <EffectComposer multisampling={0}>
      <Bloom intensity={0.85} luminanceThreshold={0.18} luminanceSmoothing={0.32} mipmapBlur />
      <Vignette eskil={false} offset={0.22} darkness={0.8} />
      <Noise opacity={0.02} blendFunction={BlendFunction.OVERLAY} />
      <SMAA />
    </EffectComposer>
  </>
);
