import React, { useMemo, useRef, useState } from 'react';
import * as THREE from 'three';
import { Canvas, useFrame } from '@react-three/fiber';
import { ContactShadows, Environment, Lightformer, RoundedBox } from '@react-three/drei';
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing';
import { BoothSpeaker } from '../types/f1';

export interface ThreeCommentatorStudioR3FProps {
  activeSpeaker: BoothSpeaker | null;
  isSpeaking: boolean;
  currentTurnQuote?: string;
  onTriggerCheer?: () => void;
}

type CameraView = 'dual' | 'lead' | 'analyst' | 'wide';

const CAMERA_PRESETS: Record<CameraView, { pos: [number, number, number]; target: [number, number, number] }> = {
  dual: { pos: [0, 1.35, 3.8], target: [0, 1.15, 0] },
  lead: { pos: [-0.85, 1.45, 2.3], target: [-0.68, 1.35, 0] },
  analyst: { pos: [0.85, 1.45, 2.3], target: [0.68, 1.35, 0] },
  wide: { pos: [0, 1.85, 5.6], target: [0, 1.1, -0.5] },
};

/** Static screen textures, drawn once (same demo content the legacy studio shows). */
function useScreenTextures() {
  return useMemo(() => {
    const make = (w: number, h: number) => {
      const c = document.createElement('canvas');
      c.width = w;
      c.height = h;
      return { canvas: c, ctx: c.getContext('2d')!, tex: new THREE.CanvasTexture(c) };
    };
    const srgb = (t: THREE.CanvasTexture) => {
      t.colorSpace = THREE.SRGBColorSpace;
      return t;
    };

    // Center video wall: F1 SHOW / PADDOCK + waveform + speaker labels.
    const center = make(1024, 512);
    const cc = center.ctx;
    cc.fillStyle = '#060a12';
    cc.fillRect(0, 0, 1024, 512);
    cc.fillStyle = '#e10600';
    cc.fillRect(0, 0, 8, 512);
    cc.fillStyle = '#ffffff';
    cc.font = 'bold 44px Arial, sans-serif';
    cc.fillText('F1 SHOW / PADDOCK', 40, 70);
    cc.fillStyle = '#5b6b85';
    cc.font = '20px monospace';
    cc.fillText('COMMENTARY STUDIO', 44, 104);
    cc.fillStyle = '#00f0ff';
    cc.fillText('DEMO', 920, 60);
    cc.strokeStyle = '#3f8ea3';
    cc.lineWidth = 3;
    cc.beginPath();
    for (let x = 40; x <= 984; x += 8) {
      const y = 250 + Math.sin(x * 0.028) * 46 + Math.sin(x * 0.011) * 28;
      if (x === 40) {
        cc.moveTo(x, y);
      } else {
        cc.lineTo(x, y);
      }
    }
    cc.stroke();
    cc.fillStyle = '#e10600';
    cc.font = 'bold 26px monospace';
    cc.fillText('CARLOS / RELATO', 40, 470);
    cc.fillStyle = '#00f0ff';
    cc.fillText('ALEX / ANÁLISIS', 700, 470);

    // Left monitor: sector sectors demo.
    const left = make(512, 384);
    const lc = left.ctx;
    lc.fillStyle = '#0a0d15';
    lc.fillRect(0, 0, 512, 384);
    lc.fillStyle = '#e10600';
    lc.font = 'bold 30px Arial, sans-serif';
    lc.fillText('SECTORES / DEMO', 28, 52);
    const teamRows: Array<[string, string, string]> = [
      ['1  VER', '#e10600', '#8be28b'],
      ['4  NOR', '#ff8000', '#c084fc'],
      ['81  PIA', '#00f0ff', '#8be28b'],
      ['44  HAM', '#facc15', '#8be28b'],
    ];
    teamRows.forEach(([label, c1, c2], i) => {
      const y = 120 + i * 62;
      lc.fillStyle = '#ffffff';
      lc.font = 'bold 24px monospace';
      lc.fillText(label, 28, y + 8);
      for (let s = 0; s < 3; s++) {
        lc.fillStyle = s === 0 ? c1 : s === 1 ? c2 : '#34d399';
        lc.fillRect(190 + s * 104, y - 16, 88, 32);
      }
    });

    // Right monitor: G-force radar.
    const right = make(512, 384);
    const rc = right.ctx;
    rc.fillStyle = '#070b13';
    rc.fillRect(0, 0, 512, 384);
    rc.strokeStyle = '#26576b';
    rc.lineWidth = 2;
    for (let r = 40; r <= 160; r += 40) {
      rc.beginPath();
      rc.arc(256, 210, r, 0, Math.PI * 2);
      rc.stroke();
    }
    rc.beginPath();
    rc.moveTo(96, 210);
    rc.lineTo(416, 210);
    rc.moveTo(256, 50);
    rc.lineTo(256, 370);
    rc.stroke();
    rc.fillStyle = '#e10600';
    rc.beginPath();
    rc.arc(330, 150, 14, 0, Math.PI * 2);
    rc.fill();
    rc.fillStyle = '#8ea3bd';
    rc.font = 'bold 24px monospace';
    rc.fillText('G-FORCE / DEMO', 28, 356);

    // Desk tablets.
    const tabletA = make(256, 192);
    const ta = tabletA.ctx;
    ta.fillStyle = '#060a12';
    ta.fillRect(0, 0, 256, 192);
    ta.fillStyle = '#e10600';
    ta.font = 'bold 24px sans-serif';
    ta.fillText('LAP 48/57', 20, 40);
    ta.fillStyle = '#fff';
    ta.font = '20px monospace';
    ta.fillText('P1 VER 1:32.410', 20, 84);
    ta.fillText('P2 NOR +1.284', 20, 120);
    ta.fillText('P3 PIA +3.412', 20, 156);

    const tabletB = make(256, 192);
    const tb = tabletB.ctx;
    tb.fillStyle = '#060a12';
    tb.fillRect(0, 0, 256, 192);
    tb.fillStyle = '#00f0ff';
    tb.font = 'bold 24px sans-serif';
    tb.fillText('MGU-K 350kW 2026', 20, 40);
    tb.strokeStyle = '#00f0ff';
    tb.lineWidth = 3;
    tb.beginPath();
    tb.moveTo(20, 140);
    tb.lineTo(80, 80);
    tb.lineTo(140, 130);
    tb.lineTo(220, 60);
    tb.stroke();

    const nameplate = (title: string, subtitle: string, color: string) => {
      const p = make(512, 128);
      const pc = p.ctx;
      pc.fillStyle = '#0a0d15';
      pc.fillRect(0, 0, 512, 128);
      pc.strokeStyle = color;
      pc.lineWidth = 8;
      pc.strokeRect(8, 8, 496, 112);
      pc.fillStyle = '#ffffff';
      pc.font = 'bold 46px Arial, sans-serif';
      pc.textAlign = 'center';
      pc.fillText(title, 256, 58);
      pc.fillStyle = color;
      pc.font = '24px monospace';
      pc.fillText(subtitle, 256, 96);
      return srgb(p.tex);
    };

    return {
      center: srgb(center.tex),
      left: srgb(left.tex),
      right: srgb(right.tex),
      tabletA: srgb(tabletA.tex),
      tabletB: srgb(tabletB.tex),
      plateCarlos: nameplate('CARLOS', 'PLAY-BY-PLAY', '#e10600'),
      plateAlex: nameplate('ALEX', 'TELEMETRÍA', '#00f0ff'),
    };
  }, []);
}

function SpeakerAvatar({
  x,
  suitColor,
  shirtColor,
  tieColor,
  skinTone,
  hairColor,
  accentColor,
  speakerLabel,
  isSpeaking,
  isActive,
}: {
  x: number;
  suitColor: string;
  shirtColor: string;
  tieColor: string;
  skinTone: string;
  hairColor: string;
  accentColor: string;
  speakerLabel: 'CARLOS' | 'ALEX';
  isSpeaking: boolean;
  isActive: boolean;
}) {
  const head = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const rim = useRef<THREE.PointLight>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (head.current) {
      const talk = isSpeaking ? Math.sin(t * 9) * 0.035 : 0;
      head.current.rotation.y = Math.sin(t * 0.6 + x) * 0.06 + talk;
      head.current.rotation.x = Math.sin(t * 1.1) * 0.02 + (isSpeaking ? Math.abs(Math.sin(t * 4.6)) * 0.03 : 0);
      head.current.position.y = 1.52 + Math.sin(t * 1.4 + x) * 0.006;
    }
    if (mouth.current) {
      const open = isSpeaking ? 0.5 + Math.abs(Math.sin(t * 11)) * 0.5 : 0.12;
      mouth.current.scale.y = open;
    }
    if (rim.current) {
      const target = isActive ? 4.2 : 1.6;
      rim.current.intensity += (target - rim.current.intensity) * 0.08;
    }
  });

  return (
    <group position={[x, 0, 0.18]}>
      <pointLight ref={rim} position={[x > 0 ? 0.5 : -0.5, 1.95, -0.75]} color={accentColor} intensity={1.6} distance={5} />
      {/* Torso: suit + shirt + tie */}
      <mesh position={[0, 1.05, 0]} castShadow>
        <capsuleGeometry args={[0.21, 0.34, 8, 20]} />
        <meshStandardMaterial color={suitColor} roughness={0.62} />
      </mesh>
      <mesh position={[0, 1.12, 0.14]}>
        <boxGeometry args={[0.17, 0.34, 0.02]} />
        <meshStandardMaterial color={shirtColor} roughness={0.5} />
      </mesh>
      <mesh position={[0, 1.08, 0.155]}>
        <boxGeometry args={[0.05, 0.24, 0.015]} />
        <meshStandardMaterial color={tieColor} roughness={0.4} />
      </mesh>
      {/* Head group: skin, hair, simple eyes, mouth, headphones */}
      <group ref={head} position={[0, 1.52, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.155, 32, 32]} />
          <meshStandardMaterial color={skinTone} roughness={0.65} />
        </mesh>
        <mesh position={[0, 0.05, -0.02]} scale={[1.08, 0.85, 1.05]}>
          <sphereGeometry args={[0.15, 24, 24, 0, Math.PI * 2, 0, Math.PI / 1.9]} />
          <meshStandardMaterial color={hairColor} roughness={0.85} />
        </mesh>
        {[-0.055, 0.055].map((ex) => (
          <group key={ex} position={[ex, 0.03, 0.135]}>
            <mesh>
              <sphereGeometry args={[0.021, 16, 16]} />
              <meshStandardMaterial color="#f8fafc" roughness={0.25} />
            </mesh>
            <mesh position={[0, 0, 0.012]}>
              <sphereGeometry args={[0.0085, 12, 12]} />
              <meshBasicMaterial color="#1a1a22" />
            </mesh>
          </group>
        ))}
        <mesh ref={mouth} position={[0, -0.055, 0.14]}>
          <boxGeometry args={[0.05, 0.03, 0.01]} />
          <meshBasicMaterial color="#7a3b34" />
        </mesh>
        {/* Headset: band + cups */}
        <mesh position={[0, 0.075, 0]} rotation={[0, 0, 0]}>
          <torusGeometry args={[0.158, 0.014, 10, 40, Math.PI]} />
          <meshStandardMaterial color="#161b26" roughness={0.5} metalness={0.4} />
        </mesh>
        {[-0.155, 0.155].map((hx) => (
          <mesh key={hx} position={[hx, 0.0, 0]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.045, 0.045, 0.035, 20]} />
            <meshStandardMaterial color="#10141d" roughness={0.6} />
          </mesh>
        ))}
        {/* Boom mic */}
        <mesh position={[speakerLabel === 'CARLOS' ? 0.09 : -0.09, -0.06, 0.1]} rotation={[0.5, 0, speakerLabel === 'CARLOS' ? -0.5 : 0.5]}>
          <cylinderGeometry args={[0.006, 0.006, 0.14, 8]} />
          <meshStandardMaterial color="#1e2430" metalness={0.6} roughness={0.4} />
        </mesh>
      </group>
    </group>
  );
}

/** Animated camera: lerps position/target between the declared presets. */
function StudioCamera({ view }: { view: CameraView }) {
  const target = useRef(new THREE.Vector3(0, 1.15, 0));
  useFrame(({ camera }) => {
    const preset = CAMERA_PRESETS[view];
    camera.position.lerp(new THREE.Vector3(...preset.pos), 0.06);
    target.current.lerp(new THREE.Vector3(...preset.target), 0.06);
    camera.lookAt(target.current);
  });
  return null;
}

/** Animated center-screen waveform (the one texture the legacy animates). */
function CenterScreenAnimator({ texture }: { texture: THREE.CanvasTexture }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const last = useRef(0);
  useMemo(() => {
    const img = texture.image as HTMLCanvasElement;
    const clone = document.createElement('canvas');
    clone.width = img.width;
    clone.height = img.height;
    clone.getContext('2d')!.drawImage(img, 0, 0);
    canvasRef.current = clone;
  }, [texture]);
  useFrame(({ clock }) => {
    const now = clock.getElapsedTime();
    if (now - last.current < 0.12 || !canvasRef.current) return;
    last.current = now;
    const ctx = canvasRef.current.getContext('2d')!;
    ctx.fillStyle = '#0a1220';
    ctx.fillRect(30, 130, 964, 220);
    ctx.strokeStyle = '#4fa8bf';
    ctx.lineWidth = 5;
    ctx.beginPath();
    const t = now;
    for (let x = 30; x <= 994; x += 10) {
      const y = 240 + Math.sin(x * 0.02 + t * 2.4) * 52 + Math.sin(x * 0.008 - t * 1.3) * 30;
      if (x === 30) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();
    texture.needsUpdate = true;
  });
  return null;
}

function MicTallyRing({ x, color, isSpeaking }: { x: number; color: string; isSpeaking: boolean }) {
  const ring = useRef<THREE.MeshBasicMaterial>(null);
  useFrame(({ clock }) => {
    if (!ring.current) return;
    const base = new THREE.Color('#334155');
    const hot = new THREE.Color(color);
    const target = isSpeaking ? hot : base;
    ring.current.color.lerp(target, 0.12);
    if (isSpeaking) {
      ring.current.opacity = 0.75 + Math.abs(Math.sin(clock.getElapsedTime() * 6)) * 0.25;
    }
  });
  return (
    <mesh position={[x, 0.87 + 0.34, 0.32 + 0.05]} rotation={[Math.PI / 3.8, 0, 0]}>
      <torusGeometry args={[0.028, 0.005, 12, 28]} />
      <meshBasicMaterial ref={ring} color="#334155" transparent />
    </mesh>
  );
}

export const ThreeCommentatorStudioR3F: React.FC<ThreeCommentatorStudioR3FProps> = ({
  activeSpeaker,
  isSpeaking,
}) => {
  const [cameraView, setCameraView] = useState<CameraView>('dual');
  const textures = useScreenTextures();

  // BoothSpeaker is 'lead' | 'color': Carlos is the lead (play-by-play), Alex the color analyst.
  const carlosActive = activeSpeaker === 'lead';
  const alexActive = activeSpeaker === 'color';

  return (
    <div className="relative h-full w-full overflow-hidden rounded-xl bg-[#07090f]">
      <Canvas
        shadows
        dpr={[1, 2]}
        camera={{ fov: 38, position: CAMERA_PRESETS.dual.pos, near: 0.1, far: 100 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 0.95;
        }}
      >
        <color attach="background" args={['#07090f']} />
        <fogExp2 attach="fog" args={['#07090f', 0.018]} />
        <StudioCamera view={cameraView} />

        {/* Local studio environment: Lightformers render into an env map — no remote HDRI. */}
        <Environment resolution={256}>
          <Lightformer intensity={2.2} color="#fff6ec" position={[0, 4, 2]} scale={[6, 3, 1]} />
          <Lightformer intensity={1.2} color="#c7e3ff" position={[-4, 2, 1]} rotation-y={Math.PI / 2} scale={[4, 2, 1]} />
          <Lightformer intensity={1.6} color="#e10600" position={[-2.5, 2, -2]} scale={[2, 4, 1]} />
          <Lightformer intensity={1.5} color="#00f0ff" position={[2.5, 2, -2]} scale={[2, 4, 1]} />
          <Lightformer intensity={0.8} color="#ffffff" position={[0, 2, 4]} scale={[5, 2, 1]} />
        </Environment>

        <hemisphereLight args={['#dceaff', '#263044', 0.55]} />
        <directionalLight
          position={[2.0, 3.5, 3.0]}
          intensity={1.5}
          color="#fff6ec"
          castShadow
          shadow-mapSize={[1024, 1024]}
          shadow-bias={-0.0005}
        />
        <pointLight position={[0, 1.3, 2.2]} intensity={6} color="#ffecd2" distance={5} />

        {/* Floor, wall, panels, neon ribs, stage */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
          <planeGeometry args={[18, 18]} />
          <meshStandardMaterial color="#141c2a" roughness={0.48} metalness={0.25} />
        </mesh>
        <RoundedBox args={[11, 4.8, 0.18]} radius={0.08} position={[0, 1.9, -2.6]} receiveShadow>
          <meshStandardMaterial color="#172334" roughness={0.8} />
        </RoundedBox>
        {Array.from({ length: 11 }, (_, i) => i - 5).map((i) => (
          <RoundedBox key={i} args={[0.78, 3.6, 0.09]} radius={0.025} position={[i * 0.94, 1.8, -2.46]}>
            <meshStandardMaterial color={i % 2 ? '#202f43' : '#192638'} roughness={0.75} />
          </RoundedBox>
        ))}
        {[-3.1, -1.35, 1.35, 3.1].map((x) => (
          <mesh key={x} position={[x, 1.8, -2.37]}>
            <boxGeometry args={[0.018, 3.25, 0.035]} />
            <meshBasicMaterial color={x < 0 ? '#ef3340' : '#65dbe5'} />
          </mesh>
        ))}
        <mesh position={[0, 0.015, -0.05]} receiveShadow>
          <cylinderGeometry args={[2.55, 2.65, 0.1, 80]} />
          <meshStandardMaterial color="#222e40" metalness={0.35} roughness={0.5} />
        </mesh>
        <mesh position={[0, 0.035, -0.05]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[2.59, 0.012, 8, 100]} />
          <meshBasicMaterial color="#44838e" />
        </mesh>

        {/* Video wall + side monitors (canvas textures) */}
        <CenterScreenAnimator texture={textures.center} />
        <group position={[0, 2.25, -2.15]}>
          <mesh>
            <boxGeometry args={[2.35, 1.2, 0.05]} />
            <meshStandardMaterial color="#07090e" metalness={0.9} roughness={0.2} />
          </mesh>
          <mesh position={[0, 0, 0.031]}>
            <planeGeometry args={[2.28, 1.13]} />
            <meshBasicMaterial map={textures.center} />
          </mesh>
        </group>
        {([
          [-1.95, textures.left, 0.32],
          [1.95, textures.right, -0.32],
        ] as const).map(([x, tex, ry]) => (
          <group key={x} position={[x, 1.95, -1.85]} rotation={[0, ry, 0]}>
            <mesh>
              <boxGeometry args={[1.35, 1.05, 0.05]} />
              <meshStandardMaterial color="#07090e" metalness={0.9} roughness={0.2} />
            </mesh>
            <mesh position={[0, 0, 0.031]}>
              <planeGeometry args={[1.27, 0.97]} />
              <meshBasicMaterial map={tex} />
            </mesh>
          </group>
        ))}

        {/* Broadcast desk */}
        <group>
          <RoundedBox args={[3.3, 0.09, 1.1]} radius={0.04} position={[0, 0.82, 0.05]} castShadow receiveShadow>
            <meshStandardMaterial color="#364357" metalness={0.35} roughness={0.32} />
          </RoundedBox>
          <mesh position={[0, 0.87, 0.05]} rotation={[-Math.PI / 2, 0, 0]}>
            <planeGeometry args={[2.9, 0.92]} />
            <meshStandardMaterial color="#1a2334" metalness={0.95} roughness={0.1} />
          </mesh>
          {/* Front branding plate */}
          <mesh position={[0, 0.45, 0.58]}>
            <planeGeometry args={[2.2, 0.5]} />
            <meshBasicMaterial color="#0d1420" />
          </mesh>
          {/* Nameplates */}
          {([
            [-0.68, textures.plateCarlos],
            [0.68, textures.plateAlex],
          ] as const).map(([x, tex]) => (
            <mesh key={x} position={[x, 0.88, 0.44]} rotation={[-0.35, 0, 0]}>
              <planeGeometry args={[0.46, 0.115]} />
              <meshBasicMaterial map={tex} />
            </mesh>
          ))}
          {/* Desk tablets */}
          {([
            [-0.68, textures.tabletA, 0.12],
            [0.68, textures.tabletB, -0.12],
          ] as const).map(([x, tex, ry]) => (
            <group key={x} position={[x, 0.87, 0.12]} rotation={[0, ry, 0]}>
              <mesh>
                <boxGeometry args={[0.36, 0.012, 0.24]} />
                <meshStandardMaterial color="#1b202c" metalness={0.9} roughness={0.2} />
              </mesh>
              <mesh position={[0, 0.115, -0.11]} rotation={[-0.28, 0, 0]}>
                <boxGeometry args={[0.36, 0.23, 0.01]} />
                <meshBasicMaterial map={tex} />
              </mesh>
            </group>
          ))}
          {/* Microphones */}
          {[-0.52, 0.52].map((x) => (
            <group key={x} position={[x, 0.87, 0.32]}>
              <mesh>
                <cylinderGeometry args={[0.06, 0.07, 0.02, 20]} />
                <meshStandardMaterial color="#111622" metalness={0.9} roughness={0.2} />
              </mesh>
              <mesh position={[0, 0.17, 0]} rotation={[0, 0, x > 0 ? -0.16 : 0.16]}>
                <cylinderGeometry args={[0.008, 0.008, 0.34, 10]} />
                <meshStandardMaterial color="#1e2430" metalness={0.8} roughness={0.3} />
              </mesh>
              <mesh position={[x > 0 ? -0.035 : 0.035, 0.34, 0.05]} rotation={[Math.PI / 3.8, 0, 0]}>
                <cylinderGeometry args={[0.026, 0.026, 0.12, 20]} />
                <meshStandardMaterial color="#090b10" roughness={0.75} metalness={0.3} />
              </mesh>
            </group>
          ))}
          <MicTallyRing x={-0.52} color="#e10600" isSpeaking={isSpeaking} />
          <MicTallyRing x={0.52} color="#00f0ff" isSpeaking={isSpeaking} />
        </group>

        {/* Commentators */}
        <SpeakerAvatar
          x={-0.68}
          suitColor="#2b3a55"
          shirtColor="#f1f5f9"
          tieColor="#e10600"
          skinTone="#dfad85"
          hairColor="#1f1a17"
          accentColor="#e10600"
          speakerLabel="CARLOS"
          isSpeaking={isSpeaking && carlosActive}
          isActive={carlosActive}
        />
        <SpeakerAvatar
          x={0.68}
          suitColor="#33415c"
          shirtColor="#e2e8f0"
          tieColor="#67e8f9"
          skinTone="#e8be9e"
          hairColor="#3d2b1f"
          accentColor="#00f0ff"
          speakerLabel="ALEX"
          isSpeaking={isSpeaking && alexActive}
          isActive={alexActive}
        />

        <ContactShadows position={[0, 0.06, 0.2]} opacity={0.55} scale={9} blur={2.4} far={2.2} />
        <EffectComposer>
          <Bloom intensity={0.55} luminanceThreshold={0.62} luminanceSmoothing={0.25} mipmapBlur />
          <Vignette eskil={false} offset={0.22} darkness={0.72} />
        </EffectComposer>
      </Canvas>

      {/* Camera view chips (same controls as the legacy overlay) */}
      <div className="absolute right-4 top-4 flex items-center gap-2">
        {(
          [
            ['dual', 'Auto Dual'],
            ['lead', 'Carlos'],
            ['analyst', 'Alex'],
            ['wide', 'Wide'],
          ] as const
        ).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setCameraView(v)}
            className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
              cameraView === v ? 'bg-[#e10600] text-white' : 'bg-black/55 text-slate-300 hover:bg-black/75'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
};
