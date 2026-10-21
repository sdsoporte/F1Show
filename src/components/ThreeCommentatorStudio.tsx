import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Maximize2, Radio } from 'lucide-react';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { BoothSpeaker } from '../types/f1';

interface ThreeCommentatorStudioProps {
  activeSpeaker: BoothSpeaker | null;
  isSpeaking: boolean;
  currentTurnQuote?: string;
  onTriggerCheer?: () => void;
}

export const ThreeCommentatorStudio: React.FC<ThreeCommentatorStudioProps> = ({
  activeSpeaker,
  isSpeaking,
  currentTurnQuote,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const [cameraView, setCameraView] = useState<'dual' | 'lead' | 'analyst' | 'wide'>('dual');
  const [isFullscreen, setIsFullscreen] = useState(false);

  // References to keep animation loop updated with React state
  const stateRef = useRef({
    activeSpeaker,
    isSpeaking,
    cameraView,
  });

  useEffect(() => {
    stateRef.current = { activeSpeaker, isSpeaking, cameraView };
  }, [activeSpeaker, isSpeaking, cameraView]);

  useEffect(() => {
    const container = mountRef.current;
    if (!container) return;

    const width = container.clientWidth || 640;
    const height = container.clientHeight || 360;

    // --- Scene, Camera, Renderer ---
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x07090f);
    scene.fog = new THREE.FogExp2(0x07090f, 0.018);

    const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
    camera.position.set(0, 1.35, 3.8);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.9;
    // A local studio environment gives skin and metal soft reflections without remote assets.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const environment = pmrem.fromScene(room, 0.04);
    scene.environment = environment.texture;
    scene.environmentIntensity = 0.35;
    room.dispose();
    pmrem.dispose();
    container.appendChild(renderer.domElement);

    // --- Studio Lighting Setup (Warm Key, Soft Fill, Dramatic Rims) ---
    const ambientLight = new THREE.HemisphereLight(0xdceaff, 0x263044, 0.9);
    scene.add(ambientLight);

    // Key Light (Warm soft studio key)
    const keyLight = new THREE.DirectionalLight(0xfff6ec, 1.7);
    keyLight.position.set(2.0, 3.5, 3.0);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    keyLight.shadow.bias = -0.0005;
    keyLight.shadow.normalBias = 0.02;
    keyLight.shadow.radius = 4;
    scene.add(keyLight);

    // Fill Light (Cool TV studio cyan-blue fill)
    const fillLight = new THREE.DirectionalLight(0xc7e3ff, 1.1);
    fillLight.position.set(-2.5, 2.0, 2.5);
    scene.add(fillLight);

    // Front Chest/Face Fill (eliminates harsh bottom-up shadows on chin)
    const faceFillLight = new THREE.PointLight(0xffecd2, 1.2, 5);
    faceFillLight.position.set(0, 1.3, 2.2);
    scene.add(faceFillLight);

    // Red Rim Backlight on Carlos
    const rimCarlos = new THREE.PointLight(0xe10600, 3.0, 5.0);
    rimCarlos.position.set(-1.1, 1.9, -0.9);
    scene.add(rimCarlos);

    // Cyan Rim Backlight on Alex
    const rimAlex = new THREE.PointLight(0x00f0ff, 2.8, 5.0);
    rimAlex.position.set(1.1, 1.9, -0.9);
    scene.add(rimAlex);

    // Overhead Softbox
    const overheadLight = new THREE.SpotLight(0xffffff, 1.5, 8, Math.PI / 4, 0.4);
    overheadLight.position.set(0, 4.2, 0.8);
    overheadLight.target.position.set(0, 1.0, 0);
    scene.add(overheadLight);
    scene.add(overheadLight.target);

    // --- Studio Architecture & Floor ---
    const floorGeo = new THREE.PlaneGeometry(18, 18);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0x141c2a,
      roughness: 0.48,
      metalness: 0.25,
    });
    const floor = new THREE.Mesh(floorGeo, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    scene.add(floor);

    // Layered architectural panels frame the video wall and catch the studio fill.
    const wallMaterial = new THREE.MeshStandardMaterial({ color: 0x172334, roughness: 0.8 });
    const wall = new THREE.Mesh(new RoundedBoxGeometry(11, 4.8, 0.18, 3, 0.08), wallMaterial);
    wall.position.set(0, 1.9, -2.6);
    wall.receiveShadow = true;
    scene.add(wall);
    for (let i = -5; i <= 5; i++) {
      const panel = new THREE.Mesh(
        new RoundedBoxGeometry(0.78, 3.6, 0.09, 2, 0.025),
        new THREE.MeshStandardMaterial({ color: i % 2 ? 0x202f43 : 0x192638, roughness: 0.75 }),
      );
      panel.position.set(i * 0.94, 1.8, -2.46);
      scene.add(panel);
    }
    for (const x of [-3.1, -1.35, 1.35, 3.1]) {
      const rib = new THREE.Mesh(
        new THREE.BoxGeometry(0.018, 3.25, 0.035),
        new THREE.MeshBasicMaterial({ color: x < 0 ? 0xef3340 : 0x65dbe5 }),
      );
      rib.position.set(x, 1.8, -2.37);
      scene.add(rib);
    }
    const stage = new THREE.Mesh(
      new THREE.CylinderGeometry(2.55, 2.65, 0.1, 80),
      new THREE.MeshStandardMaterial({ color: 0x222e40, metalness: 0.35, roughness: 0.5 }),
    );
    stage.position.set(0, 0.015, -0.05);
    stage.receiveShadow = true;
    scene.add(stage);
    const stageTrim = new THREE.Mesh(
      new THREE.TorusGeometry(2.59, 0.012, 8, 100),
      new THREE.MeshBasicMaterial({ color: 0x44838e }),
    );
    stageTrim.rotation.x = Math.PI / 2;
    stageTrim.position.y = 0.035;
    scene.add(stageTrim);

    // --- Dynamic Studio Video Walls ---
    const centerCanvas = document.createElement('canvas');
    centerCanvas.width = 1024;
    centerCanvas.height = 512;
    const centerCtx = centerCanvas.getContext('2d')!;
    const centerTexture = new THREE.CanvasTexture(centerCanvas);
    centerTexture.colorSpace = THREE.SRGBColorSpace;

    const leftCanvas = document.createElement('canvas');
    leftCanvas.width = 256;
    leftCanvas.height = 256;
    const leftCtx = leftCanvas.getContext('2d')!;
    const leftTexture = new THREE.CanvasTexture(leftCanvas);
    leftTexture.colorSpace = THREE.SRGBColorSpace;

    const rightCanvas = document.createElement('canvas');
    rightCanvas.width = 256;
    rightCanvas.height = 256;
    const rightCtx = rightCanvas.getContext('2d')!;
    const rightTexture = new THREE.CanvasTexture(rightCanvas);
    rightTexture.colorSpace = THREE.SRGBColorSpace;

    const monitorFrameMat = new THREE.MeshStandardMaterial({ color: 0x07090e, metalness: 0.9, roughness: 0.2 });

    // Center Video Wall (F1 Live Broadcast & Audio Waveform)
    const centerFrameGeo = new THREE.BoxGeometry(2.35, 1.2, 0.05);
    const centerFrame = new THREE.Mesh(centerFrameGeo, monitorFrameMat);
    centerFrame.position.set(0, 2.25, -2.15);

    const centerDisplayGeo = new THREE.PlaneGeometry(2.28, 1.13);
    const centerDisplayMat = new THREE.MeshBasicMaterial({ map: centerTexture });
    const centerDisplay = new THREE.Mesh(centerDisplayGeo, centerDisplayMat);
    centerDisplay.position.set(0, 2.25, -2.12);
    scene.add(centerFrame, centerDisplay);

    // Left Monitor (Sectors & Leaderboard)
    const sideFrameGeo = new THREE.BoxGeometry(1.35, 1.05, 0.05);
    const leftFrame = new THREE.Mesh(sideFrameGeo, monitorFrameMat);
    leftFrame.position.set(-1.95, 1.95, -1.85);
    leftFrame.rotation.y = 0.32;

    const leftDisplayGeo = new THREE.PlaneGeometry(1.27, 0.97);
    const leftDisplayMat = new THREE.MeshBasicMaterial({ map: leftTexture });
    const leftDisplay = new THREE.Mesh(leftDisplayGeo, leftDisplayMat);
    leftDisplay.position.set(-1.94, 1.95, -1.82);
    leftDisplay.rotation.y = 0.32;
    scene.add(leftFrame, leftDisplay);

    // Right Monitor (G-Force Radar & Telemetry)
    const rightFrame = new THREE.Mesh(sideFrameGeo, monitorFrameMat);
    rightFrame.position.set(1.95, 1.95, -1.85);
    rightFrame.rotation.y = -0.32;

    const rightDisplayGeo = new THREE.PlaneGeometry(1.27, 0.97);
    const rightDisplayMat = new THREE.MeshBasicMaterial({ map: rightTexture });
    const rightDisplay = new THREE.Mesh(rightDisplayGeo, rightDisplayMat);
    rightDisplay.position.set(1.94, 1.95, -1.82);
    rightDisplay.rotation.y = -0.32;
    scene.add(rightFrame, rightDisplay);

    // --- Broadcast Desk ---
    const deskGroup = new THREE.Group();

    // Curved Modern F1 Desk Top
    const deskTopGeo = new RoundedBoxGeometry(3.3, 0.09, 1.1, 4, 0.04);
    const deskTopMat = new THREE.MeshStandardMaterial({
      color: 0x364357,
      metalness: 0.35,
      roughness: 0.32,
    });
    const deskTop = new THREE.Mesh(deskTopGeo, deskTopMat);
    deskTop.position.set(0, 0.82, 0.05);
    deskTop.castShadow = true;
    deskTop.receiveShadow = true;
    deskGroup.add(deskTop);

    // Desk Glass Top Inset
    const deskGlassGeo = new THREE.PlaneGeometry(2.9, 0.92);
    const deskGlassMat = new THREE.MeshStandardMaterial({
      color: 0x1a2334,
      metalness: 0.95,
      roughness: 0.1,
      transparent: true,
      opacity: 0.5,
    });
    const deskGlass = new THREE.Mesh(deskGlassGeo, deskGlassMat);
    deskGlass.rotation.x = -Math.PI / 2;
    deskGlass.position.set(0, 0.865, 0.05);
    deskGroup.add(deskGlass);

    // Sleek Red Neon Trim along front of desk
    const deskEdgeGeo = new THREE.BoxGeometry(3.2, 0.012, 0.02);
    const deskEdgeMat = new THREE.MeshBasicMaterial({ color: 0xe10600 });
    const deskEdge = new THREE.Mesh(deskEdgeGeo, deskEdgeMat);
    deskEdge.position.set(0, 0.83, 0.6);
    deskGroup.add(deskEdge);

    // A continuous desk fascia hides the seated bodies and anchors the broadcast set.
    const fascia = new THREE.Mesh(
      new RoundedBoxGeometry(2.9, 0.64, 0.24, 5, 0.09),
      new THREE.MeshStandardMaterial({ color: 0x202d40, roughness: 0.48, metalness: 0.3 }),
    );
    fascia.position.set(0, 0.45, 0.4);
    fascia.castShadow = true;
    deskGroup.add(fascia);
    for (const x of [-1.28, 1.28]) {
      const inlay = new THREE.Mesh(
        new THREE.BoxGeometry(0.028, 0.42, 0.015),
        new THREE.MeshBasicMaterial({ color: x < 0 ? 0xef3340 : 0x65dbe5 }),
      );
      inlay.position.set(x, 0.45, 0.527);
      deskGroup.add(inlay);
    }
    const brandCanvas = document.createElement('canvas');
    brandCanvas.width = 1024;
    brandCanvas.height = 256;
    const brandCtx = brandCanvas.getContext('2d')!;
    brandCtx.fillStyle = '#172438';
    brandCtx.fillRect(0, 0, 1024, 256);
    brandCtx.fillStyle = '#ef3340';
    brandCtx.fillRect(90, 62, 12, 120);
    brandCtx.fillStyle = '#f1f5f9';
    brandCtx.font = 'italic 800 100px Arial, sans-serif';
    brandCtx.fillText('F1 SHOW', 140, 144);
    brandCtx.fillStyle = '#92a9bd';
    brandCtx.font = '24px monospace';
    brandCtx.fillText('RACE COMMENTARY STUDIO', 146, 193);
    const brandTexture = new THREE.CanvasTexture(brandCanvas);
    brandTexture.colorSpace = THREE.SRGBColorSpace;
    const brand = new THREE.Mesh(
      new THREE.PlaneGeometry(1.65, 0.4125),
      new THREE.MeshBasicMaterial({ map: brandTexture, toneMapped: false }),
    );
    brand.position.set(0, 0.45, 0.53);
    deskGroup.add(brand);

    // Nameplates on Desk (Positioned neatly without clipping edge)
    const createNameplate = (x: number, title: string, subtitle: string, colorHex: number) => {
      const pCanvas = document.createElement('canvas');
      pCanvas.width = 256;
      pCanvas.height = 64;
      const pCtx = pCanvas.getContext('2d')!;
      pCtx.fillStyle = '#0a0d15';
      pCtx.fillRect(0, 0, 256, 64);
      pCtx.strokeStyle = colorHex === 0xe10600 ? '#e10600' : '#00f0ff';
      pCtx.lineWidth = 4;
      pCtx.strokeRect(4, 4, 248, 56);

      pCtx.fillStyle = '#ffffff';
      pCtx.font = 'bold 22px Arial, sans-serif';
      pCtx.textAlign = 'center';
      pCtx.fillText(title, 128, 30);

      pCtx.fillStyle = colorHex === 0xe10600 ? '#e10600' : '#00f0ff';
      pCtx.font = '12px monospace';
      pCtx.fillText(subtitle, 128, 48);

      const pTex = new THREE.CanvasTexture(pCanvas);
      pTex.colorSpace = THREE.SRGBColorSpace;
      const pGeo = new THREE.PlaneGeometry(0.46, 0.115);
      const pMat = new THREE.MeshBasicMaterial({ map: pTex });
      const plate = new THREE.Mesh(pGeo, pMat);
      plate.position.set(x, 0.88, 0.44);
      plate.rotation.x = -0.35;
      deskGroup.add(plate);
    };

    createNameplate(-0.68, 'CARLOS', 'PLAY-BY-PLAY', 0xe10600);
    createNameplate(0.68, 'ALEX', 'TELEMETRÍA', 0x00f0ff);

    // Digital Telemetry Tablets on desk
    const createDeskTablet = (x: number, rotY: number, canvas: HTMLCanvasElement) => {
      const tabGroup = new THREE.Group();
      const baseGeo = new THREE.BoxGeometry(0.36, 0.012, 0.24);
      const baseMat = new THREE.MeshStandardMaterial({ color: 0x1b202c, metalness: 0.9, roughness: 0.2 });
      const base = new THREE.Mesh(baseGeo, baseMat);

      const scrGeo = new THREE.BoxGeometry(0.36, 0.23, 0.01);
      const scrTex = new THREE.CanvasTexture(canvas);
      scrTex.colorSpace = THREE.SRGBColorSpace;
      const scrMat = new THREE.MeshBasicMaterial({ map: scrTex });
      const scr = new THREE.Mesh(scrGeo, scrMat);
      scr.position.set(0, 0.115, -0.11);
      scr.rotation.x = -0.28;

      tabGroup.add(base, scr);
      tabGroup.position.set(x, 0.87, 0.12);
      tabGroup.rotation.y = rotY;
      deskGroup.add(tabGroup);
      return scrTex;
    };

    const tabletCanvasA = document.createElement('canvas');
    tabletCanvasA.width = 128;
    tabletCanvasA.height = 96;
    const tCtxA = tabletCanvasA.getContext('2d')!;
    tCtxA.fillStyle = '#060a12';
    tCtxA.fillRect(0, 0, 128, 96);
    tCtxA.fillStyle = '#e10600';
    tCtxA.font = 'bold 12px sans-serif';
    tCtxA.fillText('LAP 48/57', 10, 20);
    tCtxA.fillStyle = '#fff';
    tCtxA.font = '10px monospace';
    tCtxA.fillText('P1 VER 1:32.410', 10, 42);
    tCtxA.fillText('P2 NOR +1.284', 10, 60);
    tCtxA.fillText('P3 PIA +3.412', 10, 78);
    createDeskTablet(-0.68, 0.12, tabletCanvasA);

    const tabletCanvasB = document.createElement('canvas');
    tabletCanvasB.width = 128;
    tabletCanvasB.height = 96;
    const tCtxB = tabletCanvasB.getContext('2d')!;
    tCtxB.fillStyle = '#060a12';
    tCtxB.fillRect(0, 0, 128, 96);
    tCtxB.fillStyle = '#00f0ff';
    tCtxB.font = 'bold 12px sans-serif';
    tCtxB.fillText('MGU-K 350kW 2026', 10, 20);
    tCtxB.strokeStyle = '#00f0ff';
    tCtxB.beginPath();
    tCtxB.moveTo(10, 70);
    tCtxB.lineTo(40, 40);
    tCtxB.lineTo(70, 65);
    tCtxB.lineTo(110, 30);
    tCtxB.stroke();
    createDeskTablet(0.68, -0.12, tabletCanvasB);

    // Studio Microphones with Tally rings
    const createMicrophone = (x: number) => {
      const micGroup = new THREE.Group();
      const bGeo = new THREE.CylinderGeometry(0.06, 0.07, 0.02, 20);
      const bMat = new THREE.MeshStandardMaterial({ color: 0x111622, metalness: 0.9, roughness: 0.2 });
      const b = new THREE.Mesh(bGeo, bMat);

      const aGeo = new THREE.CylinderGeometry(0.008, 0.008, 0.34, 10);
      const aMat = new THREE.MeshStandardMaterial({ color: 0x1e2430, metalness: 0.8, roughness: 0.3 });
      const a = new THREE.Mesh(aGeo, aMat);
      a.position.set(0, 0.17, 0);
      a.rotation.z = x > 0 ? -0.16 : 0.16;

      const capGeo = new THREE.CylinderGeometry(0.026, 0.026, 0.12, 20);
      const capMat = new THREE.MeshStandardMaterial({ color: 0x090b10, roughness: 0.75, metalness: 0.3 });
      const cap = new THREE.Mesh(capGeo, capMat);
      cap.position.set(x > 0 ? -0.035 : 0.035, 0.34, 0.05);
      cap.rotation.x = Math.PI / 3.8;

      const ringGeo = new THREE.TorusGeometry(0.028, 0.005, 12, 28);
      const ringMat = new THREE.MeshBasicMaterial({ color: 0x334155 });
      const ring = new THREE.Mesh(ringGeo, ringMat);
      ring.position.copy(cap.position);
      ring.rotation.copy(cap.rotation);

      micGroup.add(b, a, cap, ring);
      micGroup.position.set(x, 0.87, 0.32);
      deskGroup.add(micGroup);
      return ringMat;
    };

    const micLeadRing = createMicrophone(-0.52);
    const micAnalystRing = createMicrophone(0.52);

    scene.add(deskGroup);

    // =========================================================================
    // HIGH FIDELITY STYLIZED CHARACTER BUILDER (Carlos & Alex)
    // =========================================================================

    // Shared Skin & Feature Materials
    const skinMatCarlos = new THREE.MeshStandardMaterial({
      color: 0xdfad85, // Warm golden tan
      roughness: 0.7,
      metalness: 0,
    });

    const skinMatAlex = new THREE.MeshStandardMaterial({
      color: 0xe8be9e, // Clean peach tone
      roughness: 0.7,
      metalness: 0,
    });

    // Helper: Sculpted Natural Eye with Eyelids and Blinking
    const createStylizedEye = (irisColorHex: number, x: number, y: number, z: number, skinMat: THREE.Material) => {
      const eyeGroup = new THREE.Group();
      eyeGroup.position.set(x, y, z);

      // Sclera (Subtle off-white)
      const scleraGeo = new THREE.SphereGeometry(0.022, 16, 16);
      const scleraMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.2 });
      const sclera = new THREE.Mesh(scleraGeo, scleraMat);
      sclera.scale.set(1.15, 0.72, 0.7);

      // Iris with rich color
      const irisGeo = new THREE.CircleGeometry(0.009, 24);
      const irisMat = new THREE.MeshBasicMaterial({ color: irisColorHex });
      const iris = new THREE.Mesh(irisGeo, irisMat);
      iris.position.set(0, 0, 0.016);

      // Pupil
      const pupilGeo = new THREE.CircleGeometry(0.0045, 24);
      const pupilMat = new THREE.MeshBasicMaterial({ color: 0x050505 });
      const pupil = new THREE.Mesh(pupilGeo, pupilMat);
      pupil.position.set(0, 0, 0.017);

      // Specular Glint (Makes eyes look vibrant and alive)
      const glintGeo = new THREE.CircleGeometry(0.003, 8);
      const glintMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
      const glint = new THREE.Mesh(glintGeo, glintMat);
      glint.position.set(0.003, 0.003, 0.018);

      // Eyelid for blinking animation
      const eyelidGeo = new THREE.SphereGeometry(0.023, 16, 8, 0, Math.PI * 2, 0, Math.PI * 0.5);
      const eyelid = new THREE.Mesh(eyelidGeo, skinMat);
      eyelid.position.set(0, 0.003, 0);
      eyelid.scale.set(1.12, 0.1, 0.75);

      // Upper Eyelash line / crease
      const creaseGeo = new THREE.TorusGeometry(0.021, 0.002, 6, 16, Math.PI * 0.7);
      const creaseMat = new THREE.MeshBasicMaterial({ color: 0x221810 });
      const crease = new THREE.Mesh(creaseGeo, creaseMat);
      crease.position.set(0, 0.012, 0.013);
      crease.rotation.z = Math.PI * 0.15;

      eyeGroup.add(sclera, iris, pupil, glint, eyelid, crease);
      return { eyeGroup, eyelid };
    };

    // Helper: Sculpted Natural Mouth with Lips and Dental Highlight
    const createStylizedMouth = () => {
      const mouthGroup = new THREE.Group();

      // Mouth Cavity (Dark interior)
      const cavityGeo = new THREE.SphereGeometry(0.026, 16, 16);
      cavityGeo.scale(1.2, 0.5, 0.4);
      const cavityMat = new THREE.MeshBasicMaterial({ color: 0x2b080e });
      const cavity = new THREE.Mesh(cavityGeo, cavityMat);

      // Subtle Upper Teeth Arc
      const teethGeo = new THREE.BoxGeometry(0.04, 0.006, 0.01);
      const teethMat = new THREE.MeshBasicMaterial({ color: 0xf8fafc });
      const teeth = new THREE.Mesh(teethGeo, teethMat);
      teeth.position.set(0, 0.006, 0.006);

      // Natural Lips contour
      const lipGeo = new THREE.TorusGeometry(0.028, 0.004, 8, 20, Math.PI * 0.8);
      const lipMat = new THREE.MeshStandardMaterial({ color: 0x9b4d45, roughness: 0.6 });
      const upperLip = new THREE.Mesh(lipGeo, lipMat);
      upperLip.position.set(0, 0.004, 0.01);
      upperLip.rotation.z = Math.PI * 0.1;

      mouthGroup.add(cavity, teeth, upperLip);
      return { mouthGroup, cavity, teeth };
    };

    // Helper: Anatomically Sculpted Torso with Blazer, Lapels & Tie
    const createBroadcasterTorso = (
      blazerColorHex: number,
      tieColorHex: number,
      shirtColorHex: number
    ) => {
      const torsoGroup = new THREE.Group();

      const blazerMat = new THREE.MeshStandardMaterial({ color: blazerColorHex, roughness: 0.9 });
      const chest = new THREE.Mesh(new RoundedBoxGeometry(0.49, 0.43, 0.27, 5, 0.095), blazerMat);
      chest.position.set(0, 0.96, -0.005);
      chest.castShadow = true;
      const abdomen = new THREE.Mesh(new RoundedBoxGeometry(0.42, 0.3, 0.25, 4, 0.065), blazerMat);
      abdomen.position.set(0, 0.66, -0.01);
      // Shirt front and fabric lapels sit forward of the jacket, rather than inside it.
      const shirtFront = new THREE.Mesh(
        new RoundedBoxGeometry(0.17, 0.29, 0.018, 2, 0.008),
        new THREE.MeshStandardMaterial({ color: shirtColorHex, roughness: 0.8 }),
      );
      shirtFront.position.set(0, 1.01, 0.14);
      torsoGroup.add(shirtFront);
      for (const side of [-1, 1]) {
        const shape = new THREE.Shape();
        shape.moveTo(side * 0.08, 1.17);
        shape.lineTo(side * 0.2, 1.09);
        shape.lineTo(side * 0.12, 0.99);
        shape.lineTo(side * 0.145, 0.96);
        shape.lineTo(side * 0.035, 0.84);
        shape.closePath();
        const lapel = new THREE.Mesh(
          new THREE.ShapeGeometry(shape),
          new THREE.MeshStandardMaterial({ color: blazerColorHex, roughness: 0.7, side: THREE.DoubleSide }),
        );
        lapel.position.z = 0.16;
        torsoGroup.add(lapel);
      }

      // Crisp Dress Shirt Collar
      const shirtMat = new THREE.MeshStandardMaterial({ color: shirtColorHex, roughness: 0.4 });
      const collarLGeo = new THREE.BoxGeometry(0.06, 0.1, 0.015);
      const collarL = new THREE.Mesh(collarLGeo, shirtMat);
      collarL.position.set(-0.045, 1.12, 0.14);
      collarL.rotation.z = -0.35;
      collarL.rotation.y = 0.2;

      const collarR = new THREE.Mesh(collarLGeo, shirtMat);
      collarR.position.set(0.045, 1.12, 0.14);
      collarR.rotation.z = 0.35;
      collarR.rotation.y = -0.2;

      // Silk Tie with realistic knot
      const tieKnotGeo = new THREE.BoxGeometry(0.042, 0.035, 0.025);
      const tieMat = new THREE.MeshStandardMaterial({ color: tieColorHex, roughness: 0.5 });
      const tieKnot = new THREE.Mesh(tieKnotGeo, tieMat);
      tieKnot.position.set(0, 1.1, 0.155);

      const tieBodyGeo = new THREE.BoxGeometry(0.042, 0.24, 0.012);
      const tieBody = new THREE.Mesh(tieBodyGeo, tieMat);
      tieBody.position.set(0, 0.98, 0.152);

      torsoGroup.add(chest, abdomen, collarL, collarR, tieKnot, tieBody);
      return torsoGroup;
    };

    // Helper: Sculpted Broadcaster Arm & Hand resting on the desk
    const createSculptedArm = (
      side: 'left' | 'right',
      blazerColorHex: number,
      skinMat: THREE.Material,
      holdsPen: boolean
    ) => {
      const armGroup = new THREE.Group();
      const isLeft = side === 'left';
      const dir = isLeft ? -1 : 1;
      const blazerMat = new THREE.MeshStandardMaterial({ color: blazerColorHex, roughness: 0.65 });

      // Connected sleeve segments follow a seated pose from shoulder to wrist.
      const shoulderPoint = new THREE.Vector3(dir * 0.245, 1.055, 0);
      const elbowPoint = new THREE.Vector3(dir * 0.305, 0.9, 0.19);
      const wristPoint = new THREE.Vector3(dir * 0.21, 0.895, 0.425);
      const shoulder = new THREE.Mesh(new THREE.SphereGeometry(0.075, 20, 16), blazerMat);
      shoulder.position.copy(shoulderPoint);
      const sleeve = (from: THREE.Vector3, to: THREE.Vector3, radius: number) => {
        const direction = to.clone().sub(from);
        const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, Math.max(0.01, direction.length() - radius * 2), 8, 16), blazerMat);
        mesh.position.copy(from).add(to).multiplyScalar(0.5);
        mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
        mesh.castShadow = true;
        return mesh;
      };
      const upper = sleeve(shoulderPoint, elbowPoint, 0.063);
      const forearm = sleeve(elbowPoint, wristPoint, 0.052);
      const elbow = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 12), blazerMat);
      elbow.position.copy(elbowPoint);
      armGroup.add(elbow);

      // White Shirt Cuff
      const cuffGeo = new THREE.CylinderGeometry(0.046, 0.044, 0.03, 16);
      const cuffMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 });
      const cuff = new THREE.Mesh(cuffGeo, cuffMat);
      cuff.position.copy(wristPoint);
      cuff.rotation.x = 1.35;

      // Sculpted Palm & Fingers resting on the desk
      const handGroup = new THREE.Group();
      handGroup.position.set(dir * 0.2, 0.88, 0.48);

      const palmGeo = new RoundedBoxGeometry(0.062, 0.025, 0.075, 3, 0.01);
      const palm = new THREE.Mesh(palmGeo, skinMat);
      handGroup.add(palm);

      // Relaxed resting fingers
      for (let f = -2; f <= 1; f++) {
        const fingerGeo = new THREE.CapsuleGeometry(0.007, 0.035, 6, 8);
        const finger = new THREE.Mesh(fingerGeo, skinMat);
        finger.position.set(f * 0.013, -0.005, 0.045);
        finger.rotation.x = Math.PI / 2 - 0.12;
        handGroup.add(finger);
      }

      // Sports Chronograph Watch on Carlos
      if (!isLeft) {
        const watchGeo = new THREE.CylinderGeometry(0.048, 0.048, 0.02, 16);
        const watchMat = new THREE.MeshStandardMaterial({ color: 0xd4d4d8, metalness: 0.9, roughness: 0.15 });
        const watch = new THREE.Mesh(watchGeo, watchMat);
        watch.position.copy(cuff.position);
        watch.rotation.copy(cuff.rotation);
        armGroup.add(watch);
      }

      // Broadcast Stylus / Pen in right hand
      if (holdsPen && !isLeft) {
        const penGeo = new THREE.CylinderGeometry(0.004, 0.004, 0.12, 8);
        const penMat = new THREE.MeshStandardMaterial({ color: 0xe10600, metalness: 0.8 });
        const pen = new THREE.Mesh(penGeo, penMat);
        pen.position.set(dir * 0.2, 0.9, 0.5);
        pen.rotation.z = Math.PI / 3.5;
        armGroup.add(pen);
      }

      armGroup.add(shoulder, upper, forearm, cuff, handGroup);
      return { armGroup, handGroup, upper, forearm };
    };

    // -------------------------------------------------------------------------
    // 3D AVATAR 1: CARLOS (Lead Play-by-Play Commentator)
    // -------------------------------------------------------------------------
    const leadGroup = new THREE.Group();
    leadGroup.position.set(-0.7, 0, -0.05);

    // Torso (Navy Blue Blazer, Red Racing Tie, Crisp White Shirt)
    const leadTorsoGroup = createBroadcasterTorso(0x283a54, 0xe10600, 0xffffff);
    leadGroup.add(leadTorsoGroup);

    // Arms
    const leadArmL = createSculptedArm('left', 0x283a54, skinMatCarlos, false);
    const leadArmR = createSculptedArm('right', 0x283a54, skinMatCarlos, true);
    leadGroup.add(leadArmL.armGroup, leadArmR.armGroup);

    // Neck
    const neckGeo = new THREE.CylinderGeometry(0.075, 0.082, 0.13, 20);
    const leadNeck = new THREE.Mesh(neckGeo, skinMatCarlos);
    leadNeck.position.set(0, 1.2, 0.02);
    leadGroup.add(leadNeck);

    // Head Group
    const leadHeadGroup = new THREE.Group();
    leadHeadGroup.position.set(0, 1.4, 0.02);
    leadHeadGroup.scale.setScalar(1.12);

    // Sculpted Head Cranium
    const headGeo = new THREE.SphereGeometry(0.155, 32, 32);
    headGeo.scale(0.96, 1.14, 1.02);
    const leadHead = new THREE.Mesh(headGeo, skinMatCarlos);
    leadHead.castShadow = true;
    leadHeadGroup.add(leadHead);

    // Smooth Tapered Jawline & Chin
    const jawGeo = new THREE.CapsuleGeometry(0.048, 0.065, 12, 16);
    jawGeo.scale(1.55, 0.65, 0.65);
    const leadJaw = new THREE.Mesh(jawGeo, skinMatCarlos);
    leadJaw.position.set(0, -0.085, 0.055);
    leadJaw.rotation.x = 0.28;
    leadHeadGroup.add(leadJaw);

    // Natural Sculpted Nose
    const noseBridgeGeo = new THREE.CapsuleGeometry(0.012, 0.038, 8, 12);
    const leadNoseBridge = new THREE.Mesh(noseBridgeGeo, skinMatCarlos);
    leadNoseBridge.position.set(0, -0.005, 0.165);
    leadNoseBridge.rotation.x = -0.2;

    const noseTipGeo = new THREE.SphereGeometry(0.015, 12, 12);
    const leadNoseTip = new THREE.Mesh(noseTipGeo, skinMatCarlos);
    leadNoseTip.position.set(0, -0.024, 0.175);
    leadHeadGroup.add(leadNoseBridge, leadNoseTip);

    // Eyes (Warm Rich Espresso Hazel)
    const leadEyeL = createStylizedEye(0x3e2312, -0.052, 0.032, 0.142, skinMatCarlos);
    const leadEyeR = createStylizedEye(0x3e2312, 0.052, 0.032, 0.142, skinMatCarlos);
    leadHeadGroup.add(leadEyeL.eyeGroup, leadEyeR.eyeGroup);

    // Styled Eyebrows
    const browGeo = new THREE.CapsuleGeometry(0.006, 0.045, 6, 8);
    const browMatCarlos = new THREE.MeshStandardMaterial({ color: 0x1f1712, roughness: 0.9 });
    const leadBrowL = new THREE.Mesh(browGeo, browMatCarlos);
    leadBrowL.position.set(-0.052, 0.068, 0.148);
    leadBrowL.rotation.z = -Math.PI / 2.3;
    const leadBrowR = new THREE.Mesh(browGeo, browMatCarlos);
    leadBrowR.position.set(0.052, 0.068, 0.148);
    leadBrowR.rotation.z = Math.PI / 2.3;
    leadHeadGroup.add(leadBrowL, leadBrowR);

    // Mouth with Lips & Teeth
    const leadMouthObj = createStylizedMouth();
    leadMouthObj.mouthGroup.position.set(0, -0.075, 0.155);
    leadHeadGroup.add(leadMouthObj.mouthGroup);

    // Styled Hair: Volumetric Spanish Broadcaster Pompadour
    const hairGroupCarlos = new THREE.Group();
    const hairMatCarlos = new THREE.MeshStandardMaterial({ color: 0x1c1511, roughness: 0.75 });

    // Main Hair Dome
    const hairCapGeo = new THREE.SphereGeometry(0.165, 24, 20, 0, Math.PI * 2, 0, Math.PI * 0.58);
    const hairCap = new THREE.Mesh(hairCapGeo, hairMatCarlos);
    hairCap.position.set(0, 0.06, -0.02);

    // Textured Front Pompadour Quiff (Full volume lobes)
    const quiffLobeGeo = new THREE.CapsuleGeometry(0.032, 0.08, 10, 16);
    const quiffCenter = new THREE.Mesh(quiffLobeGeo, hairMatCarlos);
    quiffCenter.position.set(0, 0.165, 0.08);
    quiffCenter.rotation.x = -Math.PI / 2.8;

    const quiffL = new THREE.Mesh(quiffLobeGeo, hairMatCarlos);
    quiffL.position.set(-0.05, 0.15, 0.07);
    quiffL.rotation.x = -Math.PI / 2.7;
    quiffL.rotation.z = 0.2;

    const quiffR = new THREE.Mesh(quiffLobeGeo, hairMatCarlos);
    quiffR.position.set(0.05, 0.15, 0.07);
    quiffR.rotation.x = -Math.PI / 2.7;
    quiffR.rotation.z = -0.2;

    hairGroupCarlos.add(hairCap, quiffCenter, quiffL, quiffR);
    leadHeadGroup.add(hairGroupCarlos);

    // Broadcast Headset (Sleek dark finish with red on-air LED)
    const headsetGroupCarlos = new THREE.Group();
    const headbandGeo = new THREE.TorusGeometry(0.185, 0.015, 12, 28, Math.PI * 0.95);
    const headsetMat = new THREE.MeshStandardMaterial({ color: 0x1f242e, metalness: 0.85, roughness: 0.25 });
    const headband = new THREE.Mesh(headbandGeo, headsetMat);
    headband.position.set(0, 0.05, -0.01);
    headband.rotation.x = 0;

    const earpadGeo = new THREE.CylinderGeometry(0.05, 0.05, 0.035, 24);
    const earpadMat = new THREE.MeshStandardMaterial({ color: 0x0f131a, roughness: 0.95 });
    const earpadL = new THREE.Mesh(earpadGeo, earpadMat);
    earpadL.position.set(-0.165, 0.01, 0);
    earpadL.rotation.z = Math.PI / 2;

    const earpadR = new THREE.Mesh(earpadGeo, earpadMat);
    earpadR.position.set(0.165, 0.01, 0);
    earpadR.rotation.z = Math.PI / 2;

    const boomGeo = new THREE.CylinderGeometry(0.005, 0.005, 0.15, 10);
    const boomCarlos = new THREE.Mesh(boomGeo, headsetMat);
    boomCarlos.position.set(-0.14, -0.05, 0.09);
    boomCarlos.rotation.x = 0.55;
    boomCarlos.rotation.z = 0.45;

    const spongeGeo = new THREE.SphereGeometry(0.016, 12, 12);
    const spongeCarlos = new THREE.Mesh(spongeGeo, earpadMat);
    spongeCarlos.position.set(-0.1, -0.11, 0.15);

    const boomTallyGeo = new THREE.TorusGeometry(0.013, 0.0035, 8, 16);
    const leadBoomTallyMat = new THREE.MeshBasicMaterial({ color: 0x444444 });
    const boomTallyCarlos = new THREE.Mesh(boomTallyGeo, leadBoomTallyMat);
    boomTallyCarlos.position.set(-0.11, -0.09, 0.13);
    boomTallyCarlos.rotation.x = Math.PI / 3;

    headsetGroupCarlos.add(headband, earpadL, earpadR, boomCarlos, spongeCarlos, boomTallyCarlos);
    leadHeadGroup.add(headsetGroupCarlos);

    leadGroup.add(leadHeadGroup);
    scene.add(leadGroup);

    // -------------------------------------------------------------------------
    // 3D AVATAR 2: ALEX (Technical & Race Telemetry Analyst)
    // -------------------------------------------------------------------------
    const analystGroup = new THREE.Group();
    analystGroup.position.set(0.7, 0, -0.05);

    // Torso (Charcoal Slate Blazer, Electric Cyan Tie, Soft Ice-Blue Shirt)
    const analystTorsoGroup = createBroadcasterTorso(0x374354, 0x00f0ff, 0xe0f2fe);
    analystGroup.add(analystTorsoGroup);

    // Arms
    const analystArmL = createSculptedArm('left', 0x374354, skinMatAlex, false);
    const analystArmR = createSculptedArm('right', 0x374354, skinMatAlex, false);
    analystGroup.add(analystArmL.armGroup, analystArmR.armGroup);

    // Neck
    const analystNeck = new THREE.Mesh(neckGeo, skinMatAlex);
    analystNeck.position.set(0, 1.2, 0.02);
    analystGroup.add(analystNeck);

    // Head Group
    const analystHeadGroup = new THREE.Group();
    analystHeadGroup.position.set(0, 1.4, 0.02);
    analystHeadGroup.scale.setScalar(1.12);

    const aHeadGeo = new THREE.SphereGeometry(0.152, 32, 32);
    aHeadGeo.scale(0.95, 1.14, 1.0);
    const analystHead = new THREE.Mesh(aHeadGeo, skinMatAlex);
    analystHead.castShadow = true;
    analystHeadGroup.add(analystHead);

    const analystJaw = new THREE.Mesh(jawGeo, skinMatAlex);
    analystJaw.position.set(0, -0.085, 0.052);
    analystJaw.rotation.x = 0.28;
    analystHeadGroup.add(analystJaw);

    // Nose
    const aNoseBridge = new THREE.Mesh(noseBridgeGeo, skinMatAlex);
    aNoseBridge.position.set(0, -0.005, 0.162);
    aNoseBridge.rotation.x = -0.2;

    const aNoseTip = new THREE.Mesh(noseTipGeo, skinMatAlex);
    aNoseTip.position.set(0, -0.024, 0.172);
    analystHeadGroup.add(aNoseBridge, aNoseTip);

    // Eyes (Sapphire / Slate Blue)
    const analystEyeL = createStylizedEye(0x1d4ed8, -0.05, 0.032, 0.14, skinMatAlex);
    const analystEyeR = createStylizedEye(0x1d4ed8, 0.05, 0.032, 0.14, skinMatAlex);
    analystHeadGroup.add(analystEyeL.eyeGroup, analystEyeR.eyeGroup);

    // Eyebrows
    const browMatAlex = new THREE.MeshStandardMaterial({ color: 0x3d271d, roughness: 0.9 });
    const aBrowL = new THREE.Mesh(browGeo, browMatAlex);
    aBrowL.position.set(-0.05, 0.068, 0.146);
    aBrowL.rotation.z = -Math.PI / 2.4;
    const aBrowR = new THREE.Mesh(browGeo, browMatAlex);
    aBrowR.position.set(0.05, 0.068, 0.146);
    aBrowR.rotation.z = Math.PI / 2.4;
    analystHeadGroup.add(aBrowL, aBrowR);

    // Mouth
    const analystMouthObj = createStylizedMouth();
    analystMouthObj.mouthGroup.position.set(0, -0.075, 0.152);
    analystHeadGroup.add(analystMouthObj.mouthGroup);

    // High-End Designer Thin Titanium Glasses (Ultra-thin wireframe + crystal clear reflection)
    const glassesGroup = new THREE.Group();
    const wireframeMat = new THREE.MeshStandardMaterial({ color: 0xd4d8e2, metalness: 0.95, roughness: 0.15 });

    // Sleek Rounded Rectangular Wire Rims
    const wireRimGeo = new THREE.TorusGeometry(0.032, 0.0028, 12, 28);
    const rimL = new THREE.Mesh(wireRimGeo, wireframeMat);
    rimL.position.set(-0.05, 0.032, 0.165);
    rimL.scale.set(1.15, 0.95, 1.0);

    const rimR = new THREE.Mesh(wireRimGeo, wireframeMat);
    rimR.position.set(0.05, 0.032, 0.165);
    rimR.scale.set(1.15, 0.95, 1.0);

    // Thin Titanium Bridge
    const bridgeGeo = new THREE.CylinderGeometry(0.002, 0.002, 0.03, 8);
    const bridge = new THREE.Mesh(bridgeGeo, wireframeMat);
    bridge.position.set(0, 0.034, 0.166);
    bridge.rotation.z = Math.PI / 2;

    // Clear Antireflective Glass Lenses
    const lensGeo = new THREE.CircleGeometry(0.03, 24);
    const lensMat = new THREE.MeshStandardMaterial({
      color: 0xe0f2fe,
      metalness: 0.8,
      roughness: 0.05,
      transparent: true,
      opacity: 0.08,
      depthWrite: false,
    });
    const lensL = new THREE.Mesh(lensGeo, lensMat);
    lensL.position.set(-0.05, 0.032, 0.166);
    lensL.scale.set(1.15, 0.95, 1.0);

    const lensR = new THREE.Mesh(lensGeo, lensMat);
    lensR.position.set(0.05, 0.032, 0.166);
    lensR.scale.set(1.15, 0.95, 1.0);

    glassesGroup.add(rimL, rimR, bridge, lensL, lensR);
    analystHeadGroup.add(glassesGroup);

    // Styled Hair: Modern Textured Side-Sweep
    const hairGroupAlex = new THREE.Group();
    const hairMatAlex = new THREE.MeshStandardMaterial({ color: 0x422a1b, roughness: 0.8 });

    const aHairCap = new THREE.Mesh(hairCapGeo, hairMatAlex);
    aHairCap.position.set(0, 0.055, -0.015);

    const sideSweepGeo = new THREE.CapsuleGeometry(0.028, 0.1, 10, 16);
    const sideSweep = new THREE.Mesh(sideSweepGeo, hairMatAlex);
    sideSweep.position.set(-0.03, 0.155, 0.07);
    sideSweep.rotation.x = -Math.PI / 2.6;
    sideSweep.rotation.z = -0.3;

    hairGroupAlex.add(aHairCap, sideSweep);
    analystHeadGroup.add(hairGroupAlex);

    // Analyst Headset with Cyan LED indicator
    const headsetGroupAlex = new THREE.Group();
    const aHeadband = new THREE.Mesh(headbandGeo, headsetMat);
    aHeadband.position.set(0, 0.05, -0.01);
    aHeadband.rotation.x = 0;

    const aEarpadL = new THREE.Mesh(earpadGeo, earpadMat);
    aEarpadL.position.set(-0.16, 0.01, 0);
    aEarpadL.rotation.z = Math.PI / 2;

    const aEarpadR = new THREE.Mesh(earpadGeo, earpadMat);
    aEarpadR.position.set(0.16, 0.01, 0);
    aEarpadR.rotation.z = Math.PI / 2;

    const aBoom = new THREE.Mesh(boomGeo, headsetMat);
    aBoom.position.set(0.14, -0.05, 0.09);
    aBoom.rotation.x = 0.55;
    aBoom.rotation.z = -0.45;

    const aSponge = new THREE.Mesh(spongeGeo, earpadMat);
    aSponge.position.set(0.1, -0.11, 0.15);

    const aBoomTallyMat = new THREE.MeshBasicMaterial({ color: 0x444444 });
    const aBoomTally = new THREE.Mesh(boomTallyGeo, aBoomTallyMat);
    aBoomTally.position.set(0.11, -0.09, 0.13);
    aBoomTally.rotation.x = Math.PI / 3;

    headsetGroupAlex.add(aHeadband, aEarpadL, aEarpadR, aBoom, aSponge, aBoomTally);
    analystHeadGroup.add(headsetGroupAlex);

    analystGroup.add(analystHeadGroup);
    scene.add(analystGroup);

    for (const [head, skin] of [[leadHeadGroup, skinMatCarlos], [analystHeadGroup, skinMatAlex]] as const) {
      for (const side of [-1, 1]) {
        const ear = new THREE.Mesh(new THREE.SphereGeometry(0.028, 16, 12), skin);
        ear.scale.set(0.65, 1.3, 0.7);
        ear.position.set(side * 0.147, -0.015, 0.015);
        head.add(ear);
      }
    }

    // -------------------------------------------------------------------------
    // ANIMATION LOOP & SIMULATION
    // -------------------------------------------------------------------------
    const startTime = performance.now();
    let animationFrameId: number;
    let screenTick = 0;
    let previousFrameTime = performance.now();
    const cameraLookTarget = new THREE.Vector3(0, 1.25, 0);

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);

      const now = performance.now();
      const deltaTime = Math.min((now - previousFrameTime) * 0.001, 0.1);
      previousFrameTime = now;
      const elapsedTime = (now - startTime) * 0.001;
      const currentSpeaker = stateRef.current.activeSpeaker;
      const isCurrentlySpeaking = stateRef.current.isSpeaking;
      const currentCameraMode = stateRef.current.cameraView;

      const isLeadActive = currentSpeaker === 'lead' && isCurrentlySpeaking;
      const isAnalystActive = currentSpeaker === 'color' && isCurrentlySpeaking;

      // Update Tally Lights on Mics & Headsets
      if (isLeadActive) {
        micLeadRing.color.setHex(0xe10600);
        leadBoomTallyMat.color.setHex(0xe10600);
      } else {
        micLeadRing.color.setHex(0x334155);
        leadBoomTallyMat.color.setHex(0x334155);
      }

      if (isAnalystActive) {
        micAnalystRing.color.setHex(0x00f0ff);
        aBoomTallyMat.color.setHex(0x00f0ff);
      } else {
        micAnalystRing.color.setHex(0x334155);
        aBoomTallyMat.color.setHex(0x334155);
      }

      // Natural Eye Blinking Simulation (every 3.6 seconds, fast 160ms blink)
      const blinkCycle = elapsedTime % 3.6;
      let blinkScale = 0.1;
      if (blinkCycle < 0.16) {
        blinkScale = Math.sin((blinkCycle / 0.16) * Math.PI) * 1.05 + 0.1;
      }
      leadEyeL.eyelid.scale.y = blinkScale;
      leadEyeR.eyelid.scale.y = blinkScale;
      analystEyeL.eyelid.scale.y = blinkScale;
      analystEyeR.eyelid.scale.y = blinkScale;

      // Update Dynamic Canvas Video Walls (every 4 frames for smooth 60fps telemetry)
      screenTick++;
      if (screenTick % 4 === 0) {
        centerCtx.fillStyle = '#0b1525';
        centerCtx.fillRect(0, 0, 1024, 512);
        centerCtx.fillStyle = '#ef3340';
        centerCtx.fillRect(44, 42, 8, 64);
        centerCtx.fillStyle = '#eff6ff';
        centerCtx.font = 'italic bold 46px Arial, sans-serif';
        centerCtx.fillText('F1 SHOW / PADDOCK', 76, 86);
        centerCtx.fillStyle = '#8ba5bd';
        centerCtx.font = '20px monospace';
        centerCtx.fillText('COMMENTARY STUDIO', 76, 120);
        centerCtx.fillText('DEMO', 894, 74);
        centerCtx.strokeStyle = '#1b3047';
        centerCtx.lineWidth = 1;
        for (let y = 170; y <= 350; y += 45) {
          centerCtx.beginPath();
          centerCtx.moveTo(44, y);
          centerCtx.lineTo(980, y);
          centerCtx.stroke();
        }
        centerCtx.strokeStyle = isLeadActive ? '#ef3340' : isAnalystActive ? '#65dbe5' : '#668ca8';
        centerCtx.lineWidth = 4;
        centerCtx.beginPath();
        for (let x = 44; x <= 980; x += 4) {
          const amp = isCurrentlySpeaking ? 58 : 12;
          const y = 260 + Math.sin(x * 0.04 + elapsedTime * (isCurrentlySpeaking ? 12 : 2)) * amp * Math.sin(x * 0.009);
          if (x === 44) centerCtx.moveTo(x, y);
          else centerCtx.lineTo(x, y);
        }
        centerCtx.stroke();
        centerCtx.fillStyle = '#14263a';
        centerCtx.fillRect(44, 398, 936, 72);
        centerCtx.fillStyle = '#d9e6f2';
        centerCtx.font = 'bold 24px monospace';
        centerCtx.fillText('CARLOS / RELATO', 70, 442);
        centerCtx.fillStyle = '#65dbe5';
        centerCtx.fillText('ALEX / ANÁLISIS', 600, 442);
        centerTexture.needsUpdate = true;

        // Left Video Wall (Sector Timings)
        leftCtx.fillStyle = '#080d16';
        leftCtx.fillRect(0, 0, 256, 256);
        leftCtx.fillStyle = '#e10600';
        leftCtx.font = 'bold 16px sans-serif';
        leftCtx.fillText('SECTORES / DEMO', 15, 28);

        const drivers = ['1 VER', '4 NOR', '81 PIA', '44 HAM'];
        drivers.forEach((drv, idx) => {
          leftCtx.fillStyle = idx === 0 ? '#10b981' : '#ffffff';
          leftCtx.font = '14px monospace';
          leftCtx.fillText(drv, 15, 65 + idx * 45);

          leftCtx.fillStyle = idx === 0 ? '#10b981' : '#eab308';
          leftCtx.fillRect(110, 52 + idx * 45, 38, 16);
          leftCtx.fillStyle = idx < 2 ? '#a855f7' : '#10b981';
          leftCtx.fillRect(155, 52 + idx * 45, 38, 16);
          leftCtx.fillStyle = '#10b981';
          leftCtx.fillRect(200, 52 + idx * 45, 38, 16);
        });
        leftTexture.needsUpdate = true;

        // Right Video Wall (G-Force Radar)
        rightCtx.fillStyle = '#080d16';
        rightCtx.fillRect(0, 0, 256, 256);
        rightCtx.strokeStyle = '#334155';
        rightCtx.lineWidth = 2;
        rightCtx.beginPath();
        rightCtx.arc(128, 128, 80, 0, Math.PI * 2);
        rightCtx.arc(128, 128, 50, 0, Math.PI * 2);
        rightCtx.arc(128, 128, 20, 0, Math.PI * 2);
        rightCtx.stroke();

        const gx = 128 + Math.cos(elapsedTime * 3) * 45;
        const gy = 128 + Math.sin(elapsedTime * 3) * 35;
        rightCtx.fillStyle = '#ef4444';
        rightCtx.beginPath();
        rightCtx.arc(gx, gy, 8, 0, Math.PI * 2);
        rightCtx.fill();

        rightCtx.fillStyle = '#ffffff';
        rightCtx.font = 'bold 16px sans-serif';
        rightCtx.fillText('G-FORCE / DEMO', 20, 240);
        rightTexture.needsUpdate = true;
      }

      // -----------------------------------------------------------------------
      // ANIMATION: CARLOS (Lead Play-by-Play Commentator)
      // -----------------------------------------------------------------------
      if (isLeadActive) {
        // High-energy speaking gestures
        leadHeadGroup.rotation.y = Math.sin(elapsedTime * 2.8) * 0.07 - 0.06;
        leadHeadGroup.rotation.x = Math.sin(elapsedTime * 3.5) * 0.035 + 0.03;
        leadHeadGroup.rotation.z = Math.sin(elapsedTime * 6) * 0.03;

        // Dynamic mouth articulation
        const mouthOpen = Math.abs(Math.sin(elapsedTime * 15)) * 0.9 + 0.35;
        leadMouthObj.mouthGroup.scale.set(1.05, mouthOpen, 1);

        // Eyebrows arching with excitement
        leadBrowL.position.y = 0.068 + Math.sin(elapsedTime * 10) * 0.008;
        leadBrowR.position.y = 0.068 + Math.sin(elapsedTime * 10) * 0.008;

        // Expressive Arm & Hand Gestures
        leadArmR.armGroup.position.y = Math.sin(elapsedTime * 6) * 0.02;
        leadArmR.armGroup.position.z = Math.sin(elapsedTime * 7) * 0.025;
        leadArmR.handGroup.rotation.x = Math.sin(elapsedTime * 10) * 0.2;

        leadTorsoGroup.position.y = Math.sin(elapsedTime * 6) * 0.012;

        // Alex looks at Carlos while Carlos is talking!
        analystHeadGroup.rotation.y = -0.22 + Math.sin(elapsedTime * 1.5) * 0.04;
        analystHeadGroup.rotation.x = 0.02;
        analystMouthObj.mouthGroup.scale.set(1, 0.24, 1);
      } else {
        // Idle breathing / looking forward
        leadHeadGroup.rotation.y = Math.sin(elapsedTime * 0.8) * 0.05 + 0.03;
        leadHeadGroup.rotation.x = Math.sin(elapsedTime * 1.2) * 0.02;
        leadHeadGroup.rotation.z = 0;
        leadMouthObj.mouthGroup.scale.set(1, 0.24, 1);
        leadBrowL.position.y = 0.068;
        leadBrowR.position.y = 0.068;
        leadArmR.armGroup.position.set(0, 0, 0);
        leadTorsoGroup.position.y = Math.sin(elapsedTime * 1.4) * 0.004;
      }

      // -----------------------------------------------------------------------
      // ANIMATION: ALEX (Technical & Race Telemetry Analyst)
      // -----------------------------------------------------------------------
      if (isAnalystActive) {
        // Analytical explanation gestures
        analystHeadGroup.rotation.y = Math.sin(elapsedTime * 2.3) * 0.06 + 0.1;
        analystHeadGroup.rotation.x = Math.sin(elapsedTime * 3) * 0.025 + 0.04;
        analystHeadGroup.rotation.z = Math.sin(elapsedTime * 5) * 0.025;

        // Articulated mouth
        const aMouthOpen = Math.abs(Math.sin(elapsedTime * 14)) * 0.8 + 0.35;
        analystMouthObj.mouthGroup.scale.set(1.05, aMouthOpen, 1);

        aBrowL.position.y = 0.068 + Math.sin(elapsedTime * 8) * 0.006;
        aBrowR.position.y = 0.068 + Math.sin(elapsedTime * 8) * 0.006;

        analystArmR.armGroup.position.y = Math.sin(elapsedTime * 5) * 0.015;
        analystTorsoGroup.position.y = Math.sin(elapsedTime * 5) * 0.008;

        // Carlos turns head towards Alex while Alex speaks!
        if (!isLeadActive) {
          leadHeadGroup.rotation.y = 0.22 + Math.sin(elapsedTime * 1.5) * 0.04;
        }
      } else if (!isLeadActive) {
        // Idle posture, checking tablet telemetry data
        analystHeadGroup.rotation.y = Math.sin(elapsedTime * 0.7 + 1) * 0.04 - 0.06;
        analystHeadGroup.rotation.x = 0.07 + Math.sin(elapsedTime * 1.1) * 0.02; // looking down at tablet
        analystHeadGroup.rotation.z = 0;
        analystMouthObj.mouthGroup.scale.set(1, 0.24, 1);
        aBrowL.position.y = 0.068;
        aBrowR.position.y = 0.068;
        analystArmR.armGroup.position.set(0, 0, 0);
        analystTorsoGroup.position.y = Math.sin(elapsedTime * 1.3) * 0.003;
      }

      // -----------------------------------------------------------------------
      // BROADCAST CAMERA TRANSITIONS (Auto Director Mode)
      // -----------------------------------------------------------------------
      let targetCamX = 0;
      let targetCamY = 1.65;
      let targetCamZ = 4.3;
      let targetLookX = 0;
      let targetLookY = 1.25;

      if (currentCameraMode === 'lead' || (currentCameraMode === 'dual' && isLeadActive && !isAnalystActive)) {
        // Tight shot on Carlos
        targetCamX = -0.7;
        targetCamY = 1.45;
        targetCamZ = 1.95;
        targetLookX = -0.7;
        targetLookY = 1.32;
      } else if (currentCameraMode === 'analyst' || (currentCameraMode === 'dual' && isAnalystActive && !isLeadActive)) {
        // Tight shot on Alex
        targetCamX = 0.7;
        targetCamY = 1.45;
        targetCamZ = 1.95;
        targetLookX = 0.7;
        targetLookY = 1.32;
      } else if (currentCameraMode === 'wide') {
        // Panoramic crane shot
        targetCamX = 0;
        targetCamY = 1.9;
        targetCamZ = 5.2;
        targetLookX = 0;
        targetLookY = 1.2;
      }

      // Preserve the two-shot on narrow panels instead of cutting off a presenter.
      targetCamZ *= Math.max(1, 1.45 / camera.aspect);
      const cameraBlend = 1 - Math.exp(-4 * deltaTime);
      camera.position.lerp(new THREE.Vector3(targetCamX, targetCamY, targetCamZ), cameraBlend);
      cameraLookTarget.lerp(new THREE.Vector3(targetLookX, targetLookY, 0), cameraBlend);
      camera.lookAt(cameraLookTarget);

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      if (!container) return;
      const newWidth = container.clientWidth;
      const newHeight = container.clientHeight;
      if (!newWidth || !newHeight) return;
      camera.aspect = newWidth / newHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);
      if (container && renderer.domElement) {
        container.removeChild(renderer.domElement);
      }
      const geometries = new Set<THREE.BufferGeometry>();
      const materials = new Set<THREE.Material>();
      const textures = new Set<THREE.Texture>();
      scene.traverse(object => {
        if (object instanceof THREE.Mesh) {
          geometries.add(object.geometry);
          const meshMaterials = Array.isArray(object.material) ? object.material : [object.material];
          for (const material of meshMaterials) {
            materials.add(material);
            for (const value of Object.values(material)) {
              if (value instanceof THREE.Texture) textures.add(value);
            }
          }
        }
      });
      geometries.forEach(geometry => geometry.dispose());
      materials.forEach(material => material.dispose());
      textures.forEach(texture => texture.dispose());
      environment.dispose();
      renderer.dispose();
      scene.clear();
    };
  }, []);

  return (
    <div
      className={`bg-zinc-950 rounded-xl overflow-hidden border border-zinc-800 shadow-2xl flex flex-col ${
        isFullscreen ? 'fixed inset-4 z-50' : 'relative h-full min-h-[420px]'
      }`}
    >
      {/* 3D WebGL Canvas Container */}
      <div ref={mountRef} className="w-full flex-1 min-h-[380px] bg-zinc-950 relative" />

      {/* Top Overlay Badge: Live Booth Status */}
      <div className="absolute top-3 left-3 flex max-w-[calc(100%-1.5rem)] items-center gap-2 bg-zinc-950/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-zinc-800/80 text-xs">
        <div className="flex items-center gap-1.5">
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isSpeaking ? 'bg-red-500 animate-ping' : 'bg-zinc-600'
            }`}
          />
          <span
            className={`w-2 h-2 rounded-full absolute ${
              isSpeaking ? 'bg-red-500' : 'bg-zinc-600'
            }`}
          />
          <span className="font-bold tracking-wider text-zinc-200">
            {isSpeaking ? 'ON AIR' : 'STUDIO IDLE'}
          </span>
        </div>
        <span className="text-zinc-600">|</span>
        <span className="text-zinc-400 font-mono text-[11px] truncate">
          {activeSpeaker === 'lead'
            ? '🎙️ Carlos (Relator Principal)'
            : activeSpeaker === 'color'
            ? '📊 Alex (Analista de Telemetría)'
            : 'Standby'}
        </span>
      </div>

      {/* Top Right: Camera Angle & Fullscreen Controls */}
      <div className="absolute top-14 right-3 sm:top-3 flex items-center gap-1.5 bg-zinc-950/85 backdrop-blur-md p-1 rounded-lg border border-zinc-800/80 text-xs">
        <button
          onClick={() => setCameraView('dual')}
          aria-pressed={cameraView === 'dual'}
          className={`px-2.5 py-1 rounded font-medium transition-colors ${
            cameraView === 'dual'
              ? 'bg-red-600 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
          title="Auto Director: cambia automáticamente al comentarista activo"
        >
          Auto Dual
        </button>
        <button
          onClick={() => setCameraView('lead')}
          aria-pressed={cameraView === 'lead'}
          className={`px-2 py-1 rounded transition-colors ${
            cameraView === 'lead'
              ? 'bg-red-600 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
          title="Primer plano de Carlos (Relator)"
        >
          Carlos
        </button>
        <button
          onClick={() => setCameraView('analyst')}
          aria-pressed={cameraView === 'analyst'}
          className={`px-2 py-1 rounded transition-colors ${
            cameraView === 'analyst'
              ? 'bg-cyan-600 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
          title="Primer plano de Alex (Telemetría)"
        >
          Alex
        </button>
        <button
          onClick={() => setCameraView('wide')}
          aria-pressed={cameraView === 'wide'}
          className={`px-2 py-1 rounded transition-colors ${
            cameraView === 'wide'
              ? 'bg-zinc-700 text-white'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
          }`}
          title="Plano general de la cabina"
        >
          Wide
        </button>
        <div className="w-[1px] h-4 bg-zinc-800 mx-0.5" />
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          aria-pressed={isFullscreen}
          className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
          title="Pantalla completa"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Bottom Subtitle / Live Quote Lower Third */}
      {currentTurnQuote && (
        <div className="absolute bottom-3 inset-x-3 bg-zinc-950/90 backdrop-blur-md p-2.5 rounded-lg border border-red-900/40 shadow-lg text-xs animate-fade-in flex items-start gap-2.5">
          <div className="p-1.5 rounded bg-red-600/20 text-red-400 shrink-0 mt-0.5">
            <Radio className="w-3.5 h-3.5 animate-pulse" />
          </div>
          <div className="flex-1 min-w-0">
            <span className="text-[10px] uppercase font-bold tracking-wider text-red-400 block font-mono">
              {activeSpeaker === 'lead' ? 'Carlos (Play-by-Play)' : activeSpeaker === 'color' ? 'Alex (Telemetría)' : 'Cabina de comentarios'}
            </span>
            <p className="text-zinc-200 line-clamp-2 leading-relaxed italic mt-0.5">
              "{currentTurnQuote}"
            </p>
          </div>
        </div>
      )}
    </div>
  );
};
