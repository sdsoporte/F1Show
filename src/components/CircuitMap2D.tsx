import React, { useState, useMemo, useEffect, useRef } from 'react';
import {
  MapPin,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Navigation,
  Play,
  Pause,
  X,
  Radio,
  Sparkles,
} from 'lucide-react';
import { LiveDriverState, SessionRecord } from '../types/f1';

interface CircuitMap2DProps {
  session: SessionRecord;
  driversState: LiveDriverState[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number | null) => void;
  currentLap: number;
  isPlaying?: boolean;
  playbackSpeed?: number;
}

interface SampledPoint {
  x: number;
  y: number;
  angle: number;
  sector: 1 | 2 | 3;
}

interface PathSampler {
  totalLength: number;
  startFinishOffsetProgress: number;
  getPointAtProgress: (progress: number) => SampledPoint;
  getPointOnPitLane: (fraction: number) => SampledPoint;
}

// Track path SVG paths for Lusail (Qatar) and COTA (Austin)
const CIRCUIT_TRACKS: Record<
  string,
  {
    name: string;
    location: string;
    turns: number;
    lengthKm: number;
    viewBox: string;
    sector1Path: string;
    sector2Path: string;
    sector3Path: string;
    pitLanePath: string;
    drsZones: Array<{ path: string; label: string; labelX: number; labelY: number }>;
    startFinish: { x: number; y: number; angle: number };
    turnMarkers: Array<{ turn: number; x: number; y: number }>;
  }
> = {
  // Lusail International Circuit (Qatar GP 9655)
  Lusail: {
    name: 'Lusail International Circuit',
    location: 'Doha, Qatar',
    turns: 16,
    lengthKm: 5.419,
    viewBox: '0 0 840 520',
    sector1Path: 'M 180 390 L 620 390 C 680 390, 710 360, 700 310 C 690 260, 650 250, 600 270',
    sector2Path: 'M 600 270 C 560 290, 520 280, 500 240 C 470 180, 420 140, 360 140 C 300 140, 260 170, 270 210',
    sector3Path: 'M 270 210 C 280 250, 240 290, 200 300 C 150 310, 130 350, 150 380 C 160 390, 170 390, 180 390',
    pitLanePath: 'M 210 412 L 590 412 C 610 412, 620 402, 620 390',
    drsZones: [
      {
        path: 'M 230 390 L 600 390',
        label: '⚡ DRS ZONE 1',
        labelX: 415,
        labelY: 372,
      },
    ],
    startFinish: { x: 380, y: 390, angle: 0 },
    turnMarkers: [
      { turn: 1, x: 672, y: 382 },
      { turn: 2, x: 708, y: 320 },
      { turn: 4, x: 610, y: 260 },
      { turn: 6, x: 520, y: 270 },
      { turn: 9, x: 440, y: 170 },
      { turn: 12, x: 330, y: 138 },
      { turn: 14, x: 260, y: 230 },
      { turn: 16, x: 155, y: 360 },
    ],
  },
  // Circuit of the Americas (Austin GP 9608)
  Austin: {
    name: 'Circuit of The Americas (COTA)',
    location: 'Austin, Texas, USA',
    turns: 20,
    lengthKm: 5.513,
    viewBox: '0 0 840 520',
    sector1Path: 'M 200 380 L 360 380 C 390 380, 420 340, 410 300 C 400 260, 440 240, 460 210 C 480 180, 520 170, 540 140',
    sector2Path: 'M 540 140 C 550 110, 590 100, 620 110 L 660 120 C 700 130, 710 160, 690 190 L 500 320',
    sector3Path: 'M 500 320 C 470 340, 430 310, 400 330 C 370 350, 340 330, 310 340 C 270 350, 230 330, 190 340 C 160 350, 170 380, 200 380',
    pitLanePath: 'M 220 404 L 350 404',
    drsZones: [
      {
        // Back straight between T11 and T12
        path: 'M 685 195 L 505 315',
        label: '⚡ DRS ZONE 1 (BACKSTRAIGHT)',
        labelX: 625,
        labelY: 240,
      },
      {
        // Main straight
        path: 'M 220 380 L 340 380',
        label: '⚡ DRS ZONE 2',
        labelX: 280,
        labelY: 416,
      },
    ],
    startFinish: { x: 280, y: 380, angle: 0 },
    turnMarkers: [
      { turn: 1, x: 418, y: 295 },
      { turn: 3, x: 450, y: 220 },
      { turn: 6, x: 530, y: 155 },
      { turn: 11, x: 705, y: 170 },
      { turn: 12, x: 560, y: 280 },
      { turn: 15, x: 460, y: 335 },
      { turn: 19, x: 230, y: 345 },
    ],
  },
};

export const CircuitMap2D: React.FC<CircuitMap2DProps> = ({
  session,
  driversState,
  selectedDriverNumber,
  onSelectDriver,
  currentLap,
  isPlaying = false,
  playbackSpeed = 1,
}) => {
  const [zoom, setZoom] = useState(1);
  const [showTurnNumbers, setShowTurnNumbers] = useState(true);
  const [showDriverTags, setShowDriverTags] = useState(true);
  const [showSectors, setShowSectors] = useState(true);
  const [showDrsZones, setShowDrsZones] = useState(true);
  const [showBattles, setShowBattles] = useState(true);
  const [localSimulation, setLocalSimulation] = useState(false);

  // Time elapsed for smooth 60 FPS advancement around the circuit
  const [simElapsed, setSimElapsed] = useState(0);
  const lastTimeRef = useRef<number>(performance.now());

  // Match circuit based on session name or default to Lusail
  const circuitKey = session.circuit_short_name?.includes('Austin') ? 'Austin' : 'Lusail';
  const circuit = CIRCUIT_TRACKS[circuitKey] || CIRCUIT_TRACKS.Lusail;

  // Single continuous closed path string (zero discontinuities)
  const fullLoopPath = useMemo(() => {
    const s1 = circuit.sector1Path;
    const s2Clean = circuit.sector2Path.replace(/^M\s*[\d.]+\s*[\d.]+\s*/, '');
    const s3Clean = circuit.sector3Path.replace(/^M\s*[\d.]+\s*[\d.]+\s*/, '');
    return `${s1} ${s2Clean} ${s3Clean} Z`;
  }, [circuit]);

  // High precision track path sampler (precomputed once on path change)
  const trackSampler = useMemo<PathSampler | null>(() => {
    if (typeof document === 'undefined') return null;

    try {
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', fullLoopPath);
      const totalLength = path.getTotalLength();

      const pitPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      pitPath.setAttribute('d', circuit.pitLanePath);
      const pitLength = pitPath.getTotalLength();

      const SAMPLES = 1200;
      const samples: SampledPoint[] = [];
      let bestDist = Infinity;
      let sfOffset = 0;

      for (let i = 0; i < SAMPLES; i++) {
        const fraction = i / SAMPLES;
        const pt = path.getPointAtLength(fraction * totalLength);
        const nextFraction = ((i + 2) % SAMPLES) / SAMPLES;
        const nextPt = path.getPointAtLength(nextFraction * totalLength);

        // Heading tangent
        const angle = Math.atan2(nextPt.y - pt.y, nextPt.x - pt.x) * (180 / Math.PI);

        // Determine sector based on fractional length
        let sector: 1 | 2 | 3 = 1;
        if (fraction < 0.35) sector = 1;
        else if (fraction < 0.70) sector = 2;
        else sector = 3;

        samples.push({ x: pt.x, y: pt.y, angle, sector });

        // Find progress closest to Start/Finish line
        const distToSF = Math.hypot(pt.x - circuit.startFinish.x, pt.y - circuit.startFinish.y);
        if (distToSF < bestDist) {
          bestDist = distToSF;
          sfOffset = fraction;
        }
      }

      // Pre-sample pit lane
      const PIT_SAMPLES = 80;
      const pitSamples: SampledPoint[] = [];
      for (let i = 0; i <= PIT_SAMPLES; i++) {
        const fraction = i / PIT_SAMPLES;
        const pt = pitPath.getPointAtLength(fraction * pitLength);
        const nextPt = pitPath.getPointAtLength(Math.min(1, (i + 1) / PIT_SAMPLES) * pitLength);
        const angle = Math.atan2(nextPt.y - pt.y, nextPt.x - pt.x) * (180 / Math.PI);
        pitSamples.push({ x: pt.x, y: pt.y, angle, sector: 1 });
      }

      return {
        totalLength,
        startFinishOffsetProgress: sfOffset,
        getPointAtProgress: (rawProgress: number) => {
          // Offset so that 0.0 is EXACTLY at the start/finish line
          const p = (((rawProgress + sfOffset) % 1.0) + 1.0) % 1.0;
          const indexF = p * SAMPLES;
          const i0 = Math.floor(indexF) % SAMPLES;
          const i1 = (i0 + 1) % SAMPLES;
          const frac = indexF - Math.floor(indexF);

          const p0 = samples[i0];
          const p1 = samples[i1];

          return {
            x: p0.x + (p1.x - p0.x) * frac,
            y: p0.y + (p1.y - p0.y) * frac,
            angle: p0.angle,
            sector: p0.sector,
          };
        },
        getPointOnPitLane: (fraction: number) => {
          const p = Math.max(0, Math.min(1, fraction));
          const indexF = p * PIT_SAMPLES;
          const i0 = Math.floor(indexF);
          const i1 = Math.min(PIT_SAMPLES, i0 + 1);
          const frac = indexF - i0;

          const p0 = pitSamples[i0] || pitSamples[0];
          const p1 = pitSamples[i1] || p0;

          return {
            x: p0.x + (p1.x - p0.x) * frac,
            y: p0.y + (p1.y - p0.y) * frac,
            angle: p0.angle,
            sector: 1,
          };
        },
      };
    } catch {
      return null;
    }
  }, [circuit, fullLoopPath]);

  // Smooth continuous 60 FPS animation loop when playing
  useEffect(() => {
    let animId: number;

    const animate = (time: number) => {
      const dt = Math.min(0.1, (time - lastTimeRef.current) * 0.001);
      lastTimeRef.current = time;

      if (isPlaying || localSimulation) {
        setSimElapsed(prev => prev + dt * playbackSpeed);
      }

      animId = requestAnimationFrame(animate);
    };

    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, localSimulation, playbackSpeed]);

  // Estimated lap duration for pace calculations (Lusail ~84s, Austin ~94s)
  const estimatedLapDuration = useMemo(() => {
    const leader = driversState[0];
    if (leader?.lastLapTime && leader.lastLapTime > 60 && leader.lastLapTime < 130) {
      return leader.lastLapTime;
    }
    return circuit.lengthKm / (220 / 3600); // ~88s
  }, [driversState, circuit.lengthKm]);

  // Helper to parse interval/gap string to seconds
  const parseGapSeconds = (gapStr: string | null | undefined, position: number): number => {
    if (!gapStr || gapStr === 'LEADER' || gapStr === '-' || gapStr === '+0.000') return 0;
    const clean = gapStr.replace('+', '').trim();
    if (clean.includes('L') || clean.includes('LAP')) {
      const laps = parseFloat(clean) || 1;
      return laps * 85;
    }
    const val = parseFloat(clean);
    if (!isNaN(val) && val >= 0) return val;
    return (position - 1) * 1.5;
  };

  // Synchronized Cars Positioning with Field Spread Normalization
  const carPositions = useMemo(() => {
    if (!trackSampler) return [];

    // Base leader progress along the track
    const leaderLapProgress = ((currentLap * 0.14) + (simElapsed / estimatedLapDuration)) % 1.0;

    // Calculate realistic field distribution across the circuit:
    // In practice/qualifying or live races, cars spread over ~70% of the lap
    // while strictly preserving close battles (gap < 1.2s)
    const runningDrivers = driversState.filter(d => d.status !== 'RETIRED');
    const gaps = runningDrivers.map(d => parseGapSeconds(d.gapToLeader, d.position));
    const maxGap = Math.max(...gaps, 1);

    // Compute cumulative delta distribution so cars don't cluster in one single straightaway
    const intervals: number[] = [];
    for (let i = 0; i < driversState.length; i++) {
      if (i === 0) {
        intervals.push(0);
      } else {
        const prevGap = parseGapSeconds(driversState[i - 1].gapToLeader, driversState[i - 1].position);
        const currGap = parseGapSeconds(driversState[i].gapToLeader, driversState[i].position);
        let delta = Math.max(0.4, currGap - prevGap);
        if (isNaN(delta) || delta <= 0) delta = 1.2;
        intervals.push(delta);
      }
    }

    let cumSum = 0;
    const cumulativeDeltas = intervals.map(d => {
      cumSum += d;
      return cumSum;
    });
    const totalCumDelta = cumSum || 1;

    // Field spans ~72% of the circuit so all 3 sectors are naturally populated
    const targetFieldSpread = 0.72;

    return driversState.map((d, index) => {
      const isLeader = d.position === 1;
      const isInPit = d.inPitLane || d.status === 'PIT';
      const gapSeconds = parseGapSeconds(d.gapToLeader, d.position);

      let x = 0;
      let y = 0;
      let angle = 0;
      let sector: 1 | 2 | 3 = 1;
      let progress = 0;

      if (isInPit) {
        // Position car along pit lane based on grid / pit box order
        const pitFraction = 0.15 + ((index * 0.038) % 0.70);
        const pt = trackSampler.getPointOnPitLane(pitFraction);
        x = pt.x;
        y = pt.y;
        angle = pt.angle;
        sector = 1;
        progress = 0;
      } else {
        // Normalized progress behind leader
        const fractionOfField = cumulativeDeltas[index] / totalCumDelta;
        const progressBehind = fractionOfField * targetFieldSpread;
        progress = (((leaderLapProgress - progressBehind) % 1.0) + 1.0) % 1.0;

        const pt = trackSampler.getPointAtProgress(progress);
        x = pt.x;
        y = pt.y;
        angle = pt.angle;
        sector = pt.sector;
      }

      // Compute anti-collision tag position:
      // Normal vector pointing perpendicular to the track tangent
      const rad = (angle * Math.PI) / 180;
      const tx = Math.cos(rad);
      const ty = Math.sin(rad);

      // Vector pointing away from track center (approx 420, 260)
      const toCenterX = 420 - x;
      const toCenterY = 260 - y;
      const n1x = -ty;
      const n1y = tx;
      const dot = n1x * toCenterX + n1y * toCenterY;
      const outX = dot < 0 ? n1x : -n1x;
      const outY = dot < 0 ? n1y : -n1y;

      // Alternate tags on the OUTSIDE and INSIDE for adjacent cars
      const isOutside = (index % 2 === 0);
      const normalOffset = isOutside ? 22 : -20;
      const tagX = x + outX * normalOffset;
      const tagY = y + outY * normalOffset;

      return {
        ...d,
        x,
        y,
        angle,
        sector,
        progress,
        isInPit,
        gapSeconds,
        tagX,
        tagY,
        isOutside,
      };
    });
  }, [trackSampler, driversState, currentLap, simElapsed, estimatedLapDuration]);

  // Selected driver object
  const selectedDriver = useMemo(() => {
    if (selectedDriverNumber === null) return null;
    return carPositions.find(c => c.driverNumber === selectedDriverNumber) || null;
  }, [carPositions, selectedDriverNumber]);

  // Detect active close battles (gap < 1.0s between consecutive cars on track)
  const activeBattles = useMemo(() => {
    if (!showBattles) return [];
    const battles: Array<{ carA: typeof carPositions[0]; carB: typeof carPositions[0]; gap: number }> = [];

    // Sort running cars on track by position
    const onTrackCars = [...carPositions]
      .filter(c => !c.isInPit && c.status !== 'RETIRED')
      .sort((a, b) => a.position - b.position);

    for (let i = 0; i < onTrackCars.length - 1; i++) {
      const carAhead = onTrackCars[i];
      const carBehind = onTrackCars[i + 1];
      const gap = Math.abs(carBehind.gapSeconds - carAhead.gapSeconds);

      if (gap > 0 && gap <= 1.2) {
        battles.push({ carA: carAhead, carB: carBehind, gap });
      }
    }
    return battles;
  }, [carPositions, showBattles]);

  const formatLapTime = (time: number | null) => {
    if (time === null || time === undefined) return '-:--.---';
    const mins = Math.floor(time / 60);
    const secs = (time % 60).toFixed(3);
    const paddedSecs = secs.length < 6 ? `0${secs}` : secs;
    return `${mins}:${paddedSecs}`;
  };

  const getTyreBadge = (compound: string) => {
    const c = (compound || 'M').toUpperCase();
    if (c.includes('SOFT') || c === 'S') return { text: 'S', bg: 'bg-red-600 text-white' };
    if (c.includes('HARD') || c === 'H') return { text: 'H', bg: 'bg-zinc-100 text-black' };
    if (c.includes('INTER') || c === 'I') return { text: 'I', bg: 'bg-green-600 text-white' };
    if (c.includes('WET') || c === 'W') return { text: 'W', bg: 'bg-blue-600 text-white' };
    return { text: 'M', bg: 'bg-yellow-500 text-black' };
  };

  return (
    <div className="bg-zinc-900/95 rounded-xl border border-zinc-800 shadow-2xl overflow-hidden flex flex-col h-full min-h-0">
      {/* Circuit Tracker Top Toolbar */}
      <div className="bg-zinc-850 px-4 py-2.5 border-b border-zinc-700/60 flex flex-wrap items-center justify-between gap-3">
        {/* Track Title and Circuit Details */}
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Navigation className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-black text-sm uppercase tracking-wider text-white">
                {circuit.name}
              </h2>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-bold">
                2D GPS SYNCHRONIZED
              </span>
            </div>
            <div className="text-[11px] text-zinc-400 flex items-center gap-2 font-mono">
              <span>{circuit.location}</span>
              <span>•</span>
              <span className="text-zinc-300 font-semibold">{circuit.lengthKm} km</span>
              <span>•</span>
              <span>{circuit.turns} Turns</span>
              <span>•</span>
              <span className="text-emerald-400">{circuit.drsZones.length} DRS Zone{circuit.drsZones.length > 1 ? 's' : ''}</span>
              <span>•</span>
              <span className="text-amber-400 font-bold">Lap {currentLap}</span>
            </div>
          </div>
        </div>

        {/* Interactive Controls & View Toggles */}
        <div className="flex items-center gap-1.5 text-xs flex-wrap">
          {/* Simulation Toggle if not actively playing */}
          <button
            onClick={() => setLocalSimulation(s => !s)}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold border transition-all cursor-pointer ${
              localSimulation || isPlaying
                ? 'bg-emerald-600/30 border-emerald-500 text-emerald-300 shadow-sm'
                : 'bg-zinc-800 border-zinc-700 text-zinc-300 hover:text-white'
            }`}
            title="Toggle Live 60 FPS Circuit Movement"
          >
            {localSimulation || isPlaying ? (
              <>
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                <span>En Vivo (60 FPS)</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 text-emerald-400" />
                <span>Simular Vuelta</span>
              </>
            )}
          </button>

          <div className="h-4 w-px bg-zinc-700 mx-1 hidden sm:block" />

          {/* Sectors Toggle */}
          <button
            onClick={() => setShowSectors(s => !s)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition-colors cursor-pointer ${
              showSectors
                ? 'bg-zinc-700 border-zinc-500 text-white shadow-sm'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Toggle Sectors S1/S2/S3 Colors"
          >
            Sectores
          </button>

          {/* Turn Numbers */}
          <button
            onClick={() => setShowTurnNumbers(t => !t)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition-colors cursor-pointer ${
              showTurnNumbers
                ? 'bg-zinc-700 border-zinc-500 text-white shadow-sm'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Toggle Turn Numbers"
          >
            Curvas (T1-T{circuit.turns})
          </button>

          {/* Driver Tags */}
          <button
            onClick={() => setShowDriverTags(d => !d)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition-colors cursor-pointer ${
              showDriverTags
                ? 'bg-zinc-700 border-zinc-500 text-white shadow-sm'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Toggle Driver Badges"
          >
            Pilotos
          </button>

          {/* DRS Zones */}
          <button
            onClick={() => setShowDrsZones(d => !d)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition-colors cursor-pointer ${
              showDrsZones
                ? 'bg-emerald-950/80 border-emerald-600 text-emerald-300'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Toggle DRS Zones"
          >
            DRS
          </button>

          {/* Battles Window */}
          <button
            onClick={() => setShowBattles(b => !b)}
            className={`px-2 py-1 rounded text-[11px] font-bold border transition-colors cursor-pointer ${
              showBattles
                ? 'bg-red-950/80 border-red-600 text-red-300'
                : 'bg-zinc-800/60 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Highlight DRS Battles (< 1.2s)"
          >
            Batallas
          </button>

          <div className="h-4 w-px bg-zinc-700 mx-1 hidden sm:block" />

          {/* Zoom Controls */}
          <div className="flex items-center gap-1 bg-zinc-950 p-0.5 rounded-lg border border-zinc-700">
            <button
              onClick={() => setZoom(z => Math.max(0.7, z - 0.15))}
              className="p-1 rounded hover:bg-zinc-800 text-zinc-300 cursor-pointer"
              title="Zoom Out"
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={() => setZoom(1)}
              className="px-1.5 py-0.5 text-[10px] font-mono text-zinc-300 hover:bg-zinc-800 rounded cursor-pointer"
              title="Reset Zoom (100%)"
            >
              {Math.round(zoom * 100)}%
            </button>
            <button
              onClick={() => setZoom(z => Math.min(2.2, z + 0.15))}
              className="p-1 rounded hover:bg-zinc-800 text-zinc-300 cursor-pointer"
              title="Zoom In"
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* Interactive SVG Canvas Area */}
      <div className="relative flex-1 min-h-0 bg-gradient-to-b from-zinc-950 to-zinc-900 overflow-hidden flex items-center justify-center p-3 select-none">
        {/* Subtle Background Radial Grid */}
        <div className="absolute inset-0 bg-[radial-gradient(#27272a_1px,transparent_1px)] [background-size:24px_24px] opacity-25 pointer-events-none" />

        <svg
          viewBox={circuit.viewBox}
          className="w-full h-full max-h-[680px] select-none transition-transform duration-150 ease-out"
          style={{ transform: `scale(${zoom})` }}
        >
          <defs>
            {/* Filters */}
            <filter id="track-shadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="6" stdDeviation="6" floodColor="#000000" floodOpacity="0.8" />
            </filter>
            <filter id="car-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
            <filter id="drs-glow" x="-30%" y="-30%" width="160%" height="160%">
              <feGaussianBlur stdDeviation="3.5" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Finish Line Pattern */}
            <pattern id="checkered-flag" width="8" height="8" patternUnits="userSpaceOnUse">
              <rect width="4" height="4" fill="#ffffff" />
              <rect x="4" width="4" height="4" fill="#000000" />
              <rect y="4" width="4" height="4" fill="#000000" />
              <rect x="4" y="4" width="4" height="4" fill="#ffffff" />
            </pattern>
          </defs>

          {/* Track Asphalt Base: Wide Dark Outline with Shadow */}
          <path
            d={fullLoopPath}
            fill="none"
            stroke="#0a0a0c"
            strokeWidth="32"
            strokeLinecap="round"
            strokeLinejoin="round"
            filter="url(#track-shadow)"
          />
          {/* Mid Curb Outline */}
          <path
            d={fullLoopPath}
            fill="none"
            stroke="#1c1917"
            strokeWidth="24"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          {/* Main Asphalt Surface */}
          <path
            d={fullLoopPath}
            fill="none"
            stroke="#27272a"
            strokeWidth="16"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Pit Lane Asphalt & Speed Limit Line */}
          <path
            d={circuit.pitLanePath}
            fill="none"
            stroke="#18181b"
            strokeWidth="10"
            strokeLinecap="round"
          />
          <path
            d={circuit.pitLanePath}
            fill="none"
            stroke="#71717a"
            strokeWidth="3"
            strokeDasharray="5 4"
            strokeLinecap="round"
          />
          <text
            x={circuitKey === 'Lusail' ? 400 : 285}
            y={circuitKey === 'Lusail' ? 426 : 418}
            fill="#71717a"
            fontSize="7.5"
            fontWeight="bold"
            fontFamily="monospace"
            textAnchor="middle"
          >
            PIT LANE (80 KM/H)
          </text>

          {/* Colored Sector Paths or Crisp White Track Line */}
          {showSectors ? (
            <>
              {/* Sector 1: Cyan */}
              <path
                d={circuit.sector1Path}
                fill="none"
                stroke="#06b6d4"
                strokeWidth="6"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="opacity-90"
              />
              {/* Sector 2: Amber */}
              <path
                d={circuit.sector2Path}
                fill="none"
                stroke="#f59e0b"
                strokeWidth="6"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="opacity-90"
              />
              {/* Sector 3: Crimson */}
              <path
                d={circuit.sector3Path}
                fill="none"
                stroke="#ef4444"
                strokeWidth="6"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="opacity-90"
              />
            </>
          ) : (
            <path
              d={fullLoopPath}
              fill="none"
              stroke="#f4f4f5"
              strokeWidth="5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="opacity-95"
            />
          )}

          {/* DRS Activation Zones Overlay with Clean Dedicated Labels */}
          {showDrsZones &&
            circuit.drsZones.map((drs, idx) => (
              <g key={idx}>
                <path
                  d={drs.path}
                  fill="none"
                  stroke="#10b981"
                  strokeWidth="8"
                  strokeDasharray="8 6"
                  strokeLinecap="round"
                  filter="url(#drs-glow)"
                  className="opacity-90 animate-pulse"
                />
                <rect
                  x={drs.labelX - 45}
                  y={drs.labelY - 7}
                  width="90"
                  height="14"
                  rx="3"
                  fill="#064e3b"
                  fillOpacity="0.85"
                  stroke="#10b981"
                  strokeWidth="0.8"
                />
                <text
                  x={drs.labelX}
                  y={drs.labelY + 3}
                  fill="#34d399"
                  fontSize="7.5"
                  fontWeight="900"
                  fontFamily="sans-serif"
                  letterSpacing="0.5"
                  textAnchor="middle"
                >
                  {drs.label}
                </text>
              </g>
            ))}

          {/* Start/Finish Line with Checkered Pattern & High-Contrast Header */}
          <g transform={`translate(${circuit.startFinish.x}, ${circuit.startFinish.y})`}>
            {/* Checkered Bar crossing track perpendicular */}
            <rect x="-3" y="-12" width="6" height="24" fill="url(#checkered-flag)" stroke="#ffffff" strokeWidth="1" />
            <rect x="-32" y="-28" width="64" height="13" rx="3" fill="#09090b" fillOpacity="0.9" stroke="#52525b" strokeWidth="1" />
            <text
              x="0"
              y="-19"
              fill="#ffffff"
              fontSize="8"
              fontWeight="900"
              fontFamily="monospace"
              textAnchor="middle"
            >
              START / FINISH
            </text>
          </g>

          {/* Turn Markers with Number Badges */}
          {showTurnNumbers &&
            circuit.turnMarkers.map(m => (
              <g key={m.turn} transform={`translate(${m.x}, ${m.y})`}>
                <circle r="7.5" fill="#09090b" stroke="#52525b" strokeWidth="1.2" />
                <text
                  textAnchor="middle"
                  dy="3"
                  fill="#e4e4e7"
                  fontSize="8.5"
                  fontWeight="900"
                  fontFamily="sans-serif"
                >
                  {m.turn}
                </text>
              </g>
            ))}

          {/* Close Battles Alert Connector Lines between battling cars */}
          {activeBattles.map(({ carA, carB, gap }, bIdx) => (
            <g key={`battle-${bIdx}`} className="pointer-events-none">
              <line
                x1={carA.x}
                y1={carA.y}
                x2={carB.x}
                y2={carB.y}
                stroke="#ef4444"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                className="animate-pulse opacity-80"
              />
              <rect
                x={(carA.x + carB.x) / 2 - 16}
                y={(carA.y + carB.y) / 2 - 7}
                width="32"
                height="13"
                rx="3"
                fill="#450a0a"
                stroke="#ef4444"
                strokeWidth="1"
              />
              <text
                x={(carA.x + carB.x) / 2}
                y={(carA.y + carB.y) / 2 + 2}
                fill="#fca5a5"
                fontSize="7.5"
                fontWeight="bold"
                fontFamily="monospace"
                textAnchor="middle"
              >
                +{gap.toFixed(2)}s
              </text>
            </g>
          ))}

          {/* Cars Synchronized on Track with Non-Overlapping Tags */}
          {carPositions.map(c => {
            const isSelected = selectedDriverNumber === c.driverNumber;
            const teamHex = `#${c.driver.team_colour || 'ffffff'}`;
            const isLeader = c.position === 1;

            return (
              <g key={c.driverNumber} className="cursor-pointer">
                {/* Connector Leader Line between car dot and driver tag */}
                {showDriverTags && (
                  <line
                    x1={c.x}
                    y1={c.y}
                    x2={c.tagX}
                    y2={c.tagY}
                    stroke={isSelected ? '#ef4444' : '#3f3f46'}
                    strokeWidth="1"
                    strokeDasharray={isSelected ? 'none' : '2 2'}
                    className="opacity-70 pointer-events-none"
                  />
                )}

                {/* Car Marker Body at (c.x, c.y) */}
                <g
                  transform={`translate(${c.x}, ${c.y})`}
                  onClick={() => onSelectDriver(isSelected ? null : c.driverNumber)}
                  className="transition-transform duration-75"
                >
                  {/* Target Pulsing Beacon for Selected Driver */}
                  {isSelected && (
                    <>
                      <circle
                        r="18"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="2"
                        className="animate-ping opacity-75"
                      />
                      <circle
                        r="14"
                        fill="none"
                        stroke="#ef4444"
                        strokeWidth="1.5"
                        strokeDasharray="4 2"
                      />
                      <line x1="-16" y1="0" x2="-10" y2="0" stroke="#ef4444" strokeWidth="2" />
                      <line x1="10" y1="0" x2="16" y2="0" stroke="#ef4444" strokeWidth="2" />
                      <line x1="0" y1="-16" x2="0" y2="-10" stroke="#ef4444" strokeWidth="2" />
                      <line x1="0" y1="10" x2="0" y2="16" stroke="#ef4444" strokeWidth="2" />
                    </>
                  )}

                  {/* Leader Ring */}
                  {isLeader && !isSelected && (
                    <circle
                      r="10"
                      fill="none"
                      stroke="#f59e0b"
                      strokeWidth="2"
                      className="animate-pulse opacity-80"
                    />
                  )}

                  {/* Car Heading Indicator Arrow (points along track tangent) */}
                  <g transform={`rotate(${c.angle})`}>
                    <polygon
                      points="8,0 3,-3 4,0 3,3"
                      fill={teamHex}
                      stroke="#ffffff"
                      strokeWidth="0.5"
                    />
                  </g>

                  {/* Main Car Dot with Glow */}
                  <circle
                    r={isSelected ? '7.5' : isLeader ? '6.5' : '5'}
                    fill={teamHex}
                    stroke="#ffffff"
                    strokeWidth={isSelected ? '2' : '1.2'}
                    filter="url(#car-glow)"
                  />

                  {/* Pit Stop Badge if Car is on Pit Lane */}
                  {c.isInPit && (
                    <g transform="translate(0, -9)">
                      <rect x="-9" y="-5" width="18" height="9" rx="2" fill="#eab308" />
                      <text
                        x="0"
                        y="2"
                        fill="#000000"
                        fontSize="6.5"
                        fontWeight="900"
                        fontFamily="monospace"
                        textAnchor="middle"
                      >
                        PIT
                      </text>
                    </g>
                  )}
                </g>

                {/* Staggered Non-Overlapping Driver Tag Badge */}
                {showDriverTags && (
                  <g
                    transform={`translate(${c.tagX}, ${c.tagY})`}
                    onClick={() => onSelectDriver(isSelected ? null : c.driverNumber)}
                    className="cursor-pointer transition-transform duration-75"
                  >
                    <rect
                      x="-18"
                      y="-7"
                      width="38"
                      height="14"
                      rx="3"
                      fill="#09090b"
                      fillOpacity="0.95"
                      stroke={isSelected ? '#ef4444' : teamHex}
                      strokeWidth={isSelected ? '1.5' : '1'}
                    />
                    <text
                      x="-14"
                      y="3.5"
                      fill="#ffffff"
                      fontSize="8.5"
                      fontWeight="bold"
                      fontFamily="monospace"
                    >
                      {c.driver.name_acronym}
                    </text>
                    <text
                      x="9"
                      y="3.5"
                      fill={teamHex}
                      fontSize="7.5"
                      fontWeight="black"
                      fontFamily="monospace"
                    >
                      {c.position}
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </svg>

        {/* Selected Driver Floating Broadcast HUD Card */}
        {selectedDriver && (
          <div className="absolute top-3 right-3 w-80 bg-zinc-900/95 backdrop-blur-md border border-zinc-700/80 rounded-xl p-3 shadow-2xl z-20 text-xs animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-zinc-800">
              <div className="flex items-center gap-2">
                <span
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: `#${selectedDriver.driver.team_colour || 'ffffff'}` }}
                />
                <span className="font-mono font-black text-sm text-white">
                  P{selectedDriver.position} • {selectedDriver.driver.full_name}
                </span>
                <span className="font-mono text-[10px] text-zinc-400">
                  #{selectedDriver.driverNumber}
                </span>
              </div>
              <button
                onClick={() => onSelectDriver(null)}
                className="text-zinc-400 hover:text-white p-1 rounded hover:bg-zinc-800 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 font-mono text-[11px]">
              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Equipo</div>
                <div className="text-white font-semibold truncate">{selectedDriver.driver.team_name}</div>
              </div>

              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Neumático</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {(() => {
                    const badge = getTyreBadge(selectedDriver.currentCompound);
                    return (
                      <span className={`w-4 h-4 rounded-full font-black text-[9px] flex items-center justify-center ${badge.bg}`}>
                        {badge.text}
                      </span>
                    );
                  })()}
                  <span className="text-zinc-300 font-bold">{selectedDriver.stintLaps} vtas</span>
                </div>
              </div>

              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Diferencia Líder</div>
                <div className="text-amber-400 font-bold">{selectedDriver.gapToLeader || 'LEADER'}</div>
              </div>

              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Intervalo Auto Del.</div>
                <div className="text-cyan-400 font-bold">{selectedDriver.interval || '-'}</div>
              </div>

              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Última Vuelta</div>
                <div className="text-white font-mono">{formatLapTime(selectedDriver.lastLapTime)}</div>
              </div>

              <div className="bg-zinc-950 p-2 rounded-lg border border-zinc-800/80">
                <div className="text-zinc-500 text-[9px] uppercase">Mejor Vuelta</div>
                <div className="text-purple-400 font-mono font-bold">{formatLapTime(selectedDriver.bestLapTime)}</div>
              </div>
            </div>

            <div className="mt-2 pt-2 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400">
              <span className="flex items-center gap-1">
                <MapPin className="w-3 h-3 text-emerald-400" />
                <span>Sector {selectedDriver.sector} {selectedDriver.isInPit ? '(En Boxes)' : '(En Pista)'}</span>
              </span>
              <span>Paradas: {selectedDriver.pitCount}</span>
            </div>
          </div>
        )}

        {/* Legend Overlay at Bottom-Left */}
        <div className="absolute bottom-3 left-3 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-lg px-3 py-2 flex flex-wrap items-center gap-3 text-[10px] font-mono shadow-lg">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
            <span className="text-zinc-300 font-semibold">Sector 1</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span className="text-zinc-300 font-semibold">Sector 2</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
            <span className="text-zinc-300 font-semibold">Sector 3</span>
          </div>
          <div className="h-3 w-px bg-zinc-700 mx-0.5" />
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-emerald-400" />
            <span className="text-emerald-300">Zona DRS</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-sm bg-yellow-400" />
            <span className="text-yellow-300">Pit Lane</span>
          </div>
          <span className="text-zinc-500">|</span>
          <span className="text-zinc-400">Clic en cualquier auto para telemetría directa</span>
        </div>
      </div>
    </div>
  );
};
