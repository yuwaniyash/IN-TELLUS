import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Sphere } from "@react-three/drei";
import { pointsInner, pointsOuter } from "./particleUtils";

const Point = ({ position, color }) => (
  <Sphere position={position} args={[0.07, 8, 8]}>
    <meshStandardMaterial
      emissive={color}
      emissiveIntensity={0.3}
      roughness={0.4}
      color={color}
    />
  </Sphere>
);

const PointCircle = () => {
  const ref = useRef(null);

  useFrame(({ clock }) => {
    if (ref.current?.rotation) {
      ref.current.rotation.z = clock.getElapsedTime() * 0.04;
    }
  });

  return (
    <group ref={ref}>
      {pointsInner.map((p) => (
        <Point key={p.idx} position={p.position} color={p.color} />
      ))}
      {pointsOuter.map((p) => (
        <Point key={p.idx} position={p.position} color={p.color} />
      ))}
    </group>
  );
};

export const ParticleRing = () => (
  <Canvas
    camera={{ position: [10, -7.5, -5] }}
    style={{ width: '100%', height: '100%', background: 'transparent' }}
  >
    <OrbitControls
      maxDistance={22}
      minDistance={8}
      enablePan={false}
      autoRotate
      autoRotateSpeed={0.4}
    />
    <directionalLight intensity={0.8} />
    <pointLight position={[-30, 0, -30]} intensity={10} />
    <PointCircle />
  </Canvas>
);