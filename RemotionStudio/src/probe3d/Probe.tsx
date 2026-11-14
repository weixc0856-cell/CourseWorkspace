import React from 'react';
import {AbsoluteFill, useCurrentFrame} from 'remotion';
import {ThreeCanvas} from '@remotion/three';
import {EffectComposer, Bloom} from '@react-three/postprocessing';

export const Probe: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: '#05070C'}}>
      <ThreeCanvas width={1080} height={1920} camera={{fov: 40, position: [0, 1.5, 6]}}>
        <color attach="background" args={['#05070C']} />
        <ambientLight intensity={0.4} />
        <directionalLight position={[3, 5, 4]} intensity={2.5} />
        <mesh rotation={[0.4, frame * 0.05, 0.2]}>
          <boxGeometry args={[1.4, 1.4, 1.4]} />
          <meshStandardMaterial color="#5FF3FF" emissive="#19C8E0" emissiveIntensity={1.4} metalness={0.4} roughness={0.2} />
        </mesh>
        <gridHelper args={[10, 20, '#1E4A55', '#102A33']} position={[0, -1.2, 0]} />
        <EffectComposer>
          <Bloom intensity={1.2} luminanceThreshold={0.5} luminanceSmoothing={0.9} mipmapBlur />
        </EffectComposer>
      </ThreeCanvas>
    </AbsoluteFill>
  );
};
