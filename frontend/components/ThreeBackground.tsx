'use client';

import { useRef, useMemo, useEffect, useState, Component, ReactNode } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Error boundary to catch Three.js errors
class ErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode; fallback: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn('Three.js background error:', error.message);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

// Floating particles component
function FloatingParticles() {
  const mesh = useRef<THREE.Points>(null!);
  const mouse = useRef({ x: 0, y: 0 });
  const count = 80;

  const particles = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const speeds = new Float32Array(count);

    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 1] = (Math.random() - 0.5) * 20;
      positions[i * 3 + 2] = (Math.random() - 0.5) * 10;
      speeds[i] = Math.random() * 0.3 + 0.1;
    }

    return { positions, speeds };
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      mouse.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      mouse.current.y = -(e.clientY / window.innerHeight) * 2 + 1;
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useFrame((state) => {
    if (!mesh.current) return;
    const time = state.clock.getElapsedTime();
    const positions = mesh.current.geometry.attributes.position.array as Float32Array;

    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      const speed = particles.speeds[i];
      positions[i3 + 1] += Math.sin(time * speed + i) * 0.002;
      positions[i3] += Math.cos(time * speed * 0.5 + i) * 0.001;
      positions[i3] += mouse.current.x * 0.002;
      positions[i3 + 1] += mouse.current.y * 0.001;
      if (positions[i3 + 1] > 10) positions[i3 + 1] = -10;
      if (positions[i3 + 1] < -10) positions[i3 + 1] = 10;
      if (positions[i3] > 10) positions[i3] = -10;
      if (positions[i3] < -10) positions[i3] = 10;
    }
    mesh.current.geometry.attributes.position.needsUpdate = true;
  });

  const geo = useMemo(() => {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(particles.positions, 3));
    return geometry;
  }, [particles.positions]);

  return (
    <points ref={mesh} geometry={geo}>
      <pointsMaterial
        size={0.05}
        color="#6366f1"
        transparent
        opacity={0.5}
        sizeAttenuation
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  );
}

// Slow rotating ring
function RotatingRing() {
  const ring = useRef<THREE.Mesh>(null!);

  useFrame((state) => {
    if (!ring.current) return;
    const time = state.clock.getElapsedTime();
    ring.current.rotation.x = Math.sin(time * 0.1) * 0.3;
    ring.current.rotation.y = time * 0.05;
  });

  return (
    <mesh ref={ring} position={[0, 0, -5]}>
      <torusGeometry args={[4, 0.015, 16, 100]} />
      <meshBasicMaterial color="#6366f1" transparent opacity={0.06} />
    </mesh>
  );
}

// Main scene
function Scene() {
  return (
    <>
      <FloatingParticles />
      <RotatingRing />
    </>
  );
}

// Fallback when Three.js fails
function FallbackBackground() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0">
      <div className="absolute inset-0 bg-[#0a0a1a]" />
      {/* Static decorative dots */}
      <div className="absolute left-1/4 top-1/4 h-1 w-1 rounded-full bg-indigo-500/30" />
      <div className="absolute right-1/3 top-1/3 h-1 w-1 rounded-full bg-purple-500/30" />
      <div className="absolute bottom-1/4 left-1/3 h-1 w-1 rounded-full bg-indigo-500/20" />
    </div>
  );
}

// Main background component
export function ThreeBackground() {
  const [mounted, setMounted] = useState(false);
  const [hasWebGL, setHasWebGL] = useState(true);

  useEffect(() => {
    // Check WebGL support
    try {
      const canvas = document.createElement('canvas');
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
      if (!gl) {
        setHasWebGL(false);
      }
    } catch {
      setHasWebGL(false);
    }
    setMounted(true);
  }, []);

  if (!mounted || !hasWebGL) {
    return <FallbackBackground />;
  }

  return (
    <ErrorBoundary fallback={<FallbackBackground />}>
      <div className="pointer-events-none fixed inset-0 z-0">
        <Canvas
          camera={{ position: [0, 0, 5], fov: 60 }}
          dpr={[1, 1.5]}
          gl={{
            antialias: true,
            alpha: true,
            powerPreference: 'high-performance',
          }}
          style={{ background: 'transparent' }}
        >
          <Scene />
        </Canvas>
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#0a0a1a]/80" />
      </div>
    </ErrorBoundary>
  );
}
