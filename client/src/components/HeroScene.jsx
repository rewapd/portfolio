import { Canvas } from '@react-three/fiber';
import { Float, MeshDistortMaterial, OrbitControls, Sparkles } from '@react-three/drei';

export default function HeroScene() {
  return (
    <Canvas camera={{ position: [0, 0, 5], fov: 50 }}>
      <ambientLight intensity={1.2} />
      <directionalLight position={[3, 3, 5]} intensity={2.2} />
      <Sparkles count={120} scale={[6, 6, 6]} size={2} speed={0.6} color="#a78bfa" />
      <Float speed={2.4} rotationIntensity={1.5} floatIntensity={2.5}>
        <mesh>
          <icosahedronGeometry args={[1.7, 2]} />
          <MeshDistortMaterial
            color="#8b5cf6"
            emissive="#312e81"
            emissiveIntensity={0.7}
            roughness={0.15}
            metalness={0.75}
            distort={0.5}
            speed={2}
          />
        </mesh>
      </Float>
      <Float speed={1.8} rotationIntensity={1.4} floatIntensity={1.8} position={[2.4, -1.2, -1]}>
        <mesh>
          <torusKnotGeometry args={[0.7, 0.18, 160, 22]} />
          <meshStandardMaterial color="#67e8f9" metalness={0.7} roughness={0.2} />
        </mesh>
      </Float>
      <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={1.5} />
    </Canvas>
  );
}
