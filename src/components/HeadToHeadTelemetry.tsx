import React, { useState } from 'react';
import {
  Gauge,
  Zap,
  Activity,
  ArrowRightLeft,
  ChevronRight,
  TrendingDown,
  TrendingUp,
  Cpu,
  Flame,
} from 'lucide-react';
import { LiveDriverState } from '../types/f1';

interface HeadToHeadTelemetryProps {
  driversState: LiveDriverState[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number | null) => void;
  currentLap: number;
}

export const HeadToHeadTelemetry: React.FC<HeadToHeadTelemetryProps> = ({
  driversState,
  selectedDriverNumber,
  onSelectDriver,
  currentLap,
}) => {
  // Select driver A (defaults to selected or P1) and driver B (defaults to P2)
  const defaultDriverA = selectedDriverNumber || driversState[0]?.driverNumber || 1;
  const [driverANum, setDriverANum] = useState<number>(defaultDriverA);
  const [driverBNum, setDriverBNum] = useState<number>(
    driversState[1]?.driverNumber || 4
  );

  const driverA = driversState.find(d => d.driverNumber === driverANum) || driversState[0];
  const driverB = driversState.find(d => d.driverNumber === driverBNum) || driversState[1];

  // Simulated telemetry traces across 20 track sample points (Austin COTA lap)
  const generateTelemetryPoints = (seedA: number, seedB: number) => {
    const points = [];
    const baseSpeeds = [
      315, 324, 110, 145, 230, 260, 275, 185, 210, 120, 290, 335, 95, 130, 210, 240, 160, 195, 255, 310
    ];

    for (let i = 0; i < baseSpeeds.length; i++) {
      const dist = (i / baseSpeeds.length) * 5513; // track length in meters
      const speedA = Math.round(baseSpeeds[i] + Math.sin(i * 1.5 + seedA) * 12);
      const speedB = Math.round(baseSpeeds[i] + Math.cos(i * 1.2 + seedB) * 10);
      const throttleA = speedA > 200 ? 100 : Math.max(0, Math.round((speedA / 200) * 100));
      const throttleB = speedB > 200 ? 100 : Math.max(0, Math.round((speedB / 200) * 100));
      const brakeA = speedA < 160 ? Math.min(100, Math.round(((160 - speedA) / 80) * 100)) : 0;
      const brakeB = speedB < 160 ? Math.min(100, Math.round(((160 - speedB) / 80) * 100)) : 0;
      const gearA = Math.min(8, Math.max(2, Math.floor(speedA / 42) + 1));
      const gearB = Math.min(8, Math.max(2, Math.floor(speedB / 42) + 1));
      const delta = +(Math.sin(i * 0.4) * 0.28).toFixed(3);

      points.push({
        dist: Math.round(dist),
        corner: `T${i + 1}`,
        speedA,
        speedB,
        throttleA,
        throttleB,
        brakeA,
        brakeB,
        gearA,
        gearB,
        delta,
      });
    }
    return points;
  };

  const telemetryData = generateTelemetryPoints(driverANum * 0.3, driverBNum * 0.5);

  const swapDrivers = () => {
    const temp = driverANum;
    setDriverANum(driverBNum);
    setDriverBNum(temp);
  };

  if (!driverA || !driverB) {
    return <div className="p-8 text-center text-zinc-500">Cargando telemetría...</div>;
  }

  const formatLap = (time: number | null) => {
    if (!time) return '-:--.---';
    const m = Math.floor(time / 60);
    const s = (time % 60).toFixed(3);
    return `${m}:${s.padStart(6, '0')}`;
  };

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header Selector */}
      <div className="bg-zinc-850 p-4 border-b border-zinc-700/60 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          <h2 className="font-black text-sm uppercase tracking-wider text-white">
            Head-to-Head Telemetry Cockpit
          </h2>
          <span className="text-xs font-mono text-zinc-400">
            Lap {currentLap} Delta Analysis
          </span>
        </div>

        {/* Driver Selection Pills */}
        <div className="flex items-center gap-2">
          {/* Driver A */}
          <div className="flex items-center gap-1.5 bg-zinc-950 px-2.5 py-1.5 rounded-lg border border-red-500/40">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
            <select
              value={driverANum}
              onChange={e => setDriverANum(Number(e.target.value))}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer"
            >
              {driversState.map(d => (
                <option key={`a-${d.driverNumber}`} value={d.driverNumber} className="bg-zinc-900 text-white">
                  P{d.position} - #{d.driverNumber} {d.driver.name_acronym} ({d.driver.team_name})
                </option>
              ))}
            </select>
          </div>

          {/* Swap Button */}
          <button
            onClick={swapDrivers}
            className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
            title="Swap Driver A and B"
          >
            <ArrowRightLeft className="w-3.5 h-3.5" />
          </button>

          {/* Driver B */}
          <div className="flex items-center gap-1.5 bg-zinc-950 px-2.5 py-1.5 rounded-lg border border-cyan-500/40">
            <span className="w-2.5 h-2.5 rounded-full bg-cyan-400" />
            <select
              value={driverBNum}
              onChange={e => setDriverBNum(Number(e.target.value))}
              className="bg-transparent text-xs font-bold text-white focus:outline-none cursor-pointer"
            >
              {driversState.map(d => (
                <option key={`b-${d.driverNumber}`} value={d.driverNumber} className="bg-zinc-900 text-white">
                  P{d.position} - #{d.driverNumber} {d.driver.name_acronym} ({d.driver.team_name})
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Main Comparison Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Battle Cards Summary */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Driver A Card */}
          <div className="bg-zinc-950 p-4 rounded-xl border border-red-900/40 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-red-600/10 rounded-full blur-xl pointer-events-none" />
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-red-400">Driver Car A</span>
                <h3 className="text-lg font-black text-white">
                  #{driverA.driverNumber} {driverA.driver.full_name}
                </h3>
                <p className="text-xs text-zinc-400">{driverA.driver.team_name}</p>
              </div>
              <div className="text-right">
                <span className="text-2xl font-black text-white font-mono">P{driverA.position}</span>
                <p className="text-xs font-mono text-zinc-400">{formatLap(driverA.bestLapTime)}</p>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Top Speed</span>
                <span className="font-mono font-bold text-white">338 km/h</span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Tyre Life</span>
                <span className="font-mono font-bold text-yellow-400">
                  {driverA.currentCompound || 'M'} ({driverA.stintLaps || 1} Laps)
                </span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Gap to P1</span>
                <span className="font-mono font-bold text-white">
                  {driverA.position === 1 ? 'LEADER' : driverA.gapToLeader || '+0.000s'}
                </span>
              </div>
            </div>
          </div>

          {/* Driver B Card */}
          <div className="bg-zinc-950 p-4 rounded-xl border border-cyan-900/40 relative overflow-hidden">
            <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-600/10 rounded-full blur-xl pointer-events-none" />
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] font-black uppercase tracking-wider text-cyan-400">Driver Car B</span>
                <h3 className="text-lg font-black text-white">
                  #{driverB.driverNumber} {driverB.driver.full_name}
                </h3>
                <p className="text-xs text-zinc-400">{driverB.driver.team_name}</p>
              </div>
              <div className="text-right">
                <span className="text-2xl font-black text-white font-mono">P{driverB.position}</span>
                <p className="text-xs font-mono text-zinc-400">{formatLap(driverB.bestLapTime)}</p>
              </div>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 text-center text-xs">
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Top Speed</span>
                <span className="font-mono font-bold text-white">334 km/h</span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Tyre Life</span>
                <span className="font-mono font-bold text-yellow-400">
                  {driverB.currentCompound || 'M'} ({driverB.stintLaps || 1} Laps)
                </span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-zinc-800">
                <span className="text-[10px] text-zinc-400 block">Delta to Car A</span>
                <span className="font-mono font-bold text-emerald-400">
                  {driverB.interval || '+0.420s'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Speed Trace Graph (SVG) */}
        <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800 shadow-md">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Gauge className="w-4 h-4 text-emerald-400" />
              <h4 className="text-xs font-black uppercase tracking-wider text-white">
                Telemetry Speed Trace (km/h vs Lap Distance)
              </h4>
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-red-400">
                <span className="w-3 h-0.5 bg-red-500 inline-block" /> #{driverA.driver.name_acronym}
              </span>
              <span className="flex items-center gap-1.5 text-cyan-400">
                <span className="w-3 h-0.5 bg-cyan-400 inline-block" /> #{driverB.driver.name_acronym}
              </span>
            </div>
          </div>

          {/* SVG Speed Chart */}
          <div className="w-full h-44 relative bg-zinc-900/60 rounded-lg p-2 border border-zinc-800/80">
            <svg viewBox="0 0 1000 160" className="w-full h-full overflow-visible" preserveAspectRatio="none">
              {/* Speed Grid Lines */}
              <line x1="0" y1="20" x2="1000" y2="20" stroke="#27272a" strokeDasharray="4 4" />
              <line x1="0" y1="60" x2="1000" y2="60" stroke="#27272a" strokeDasharray="4 4" />
              <line x1="0" y1="100" x2="1000" y2="100" stroke="#27272a" strokeDasharray="4 4" />
              <line x1="0" y1="140" x2="1000" y2="140" stroke="#27272a" strokeDasharray="4 4" />

              <text x="10" y="24" fill="#71717a" fontSize="10" fontFamily="monospace">320 km/h</text>
              <text x="10" y="64" fill="#71717a" fontSize="10" fontFamily="monospace">240 km/h</text>
              <text x="10" y="104" fill="#71717a" fontSize="10" fontFamily="monospace">160 km/h</text>
              <text x="10" y="144" fill="#71717a" fontSize="10" fontFamily="monospace">80 km/h</text>

              {/* Driver B Trace */}
              <polyline
                fill="none"
                stroke="#22d3ee"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={telemetryData
                  .map((p, idx) => {
                    const x = (idx / (telemetryData.length - 1)) * 980 + 10;
                    // Map 80 - 340 km/h to Y 150 - 15
                    const y = 150 - ((p.speedB - 80) / 260) * 135;
                    return `${x},${y}`;
                  })
                  .join(' ')}
              />

              {/* Driver A Trace */}
              <polyline
                fill="none"
                stroke="#ef4444"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                points={telemetryData
                  .map((p, idx) => {
                    const x = (idx / (telemetryData.length - 1)) * 980 + 10;
                    const y = 150 - ((p.speedA - 80) / 260) * 135;
                    return `${x},${y}`;
                  })
                  .join(' ')}
              />
            </svg>
          </div>
        </div>

        {/* Throttle, Brake & Gear Trace */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Throttle & Brake */}
          <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800">
            <h4 className="text-xs font-black uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-yellow-400" />
              Pedal Application (Throttle % & Brake %)
            </h4>
            <div className="space-y-3">
              <div>
                <div className="flex justify-between text-[11px] font-mono mb-1">
                  <span className="text-red-400 font-bold">#{driverA.driver.name_acronym} Throttle</span>
                  <span className="text-white">98% Avg Straight</span>
                </div>
                <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden border border-zinc-800">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: '92%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] font-mono mb-1">
                  <span className="text-cyan-400 font-bold">#{driverB.driver.name_acronym} Throttle</span>
                  <span className="text-white">94% Avg Straight</span>
                </div>
                <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden border border-zinc-800">
                  <div className="bg-emerald-500 h-full rounded-full" style={{ width: '88%' }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] font-mono mb-1">
                  <span className="text-red-400 font-bold">Braking Pressure (Peak G-Force)</span>
                  <span className="text-white font-mono">5.2 G vs 5.0 G</span>
                </div>
                <div className="w-full bg-zinc-900 rounded-full h-2 overflow-hidden border border-zinc-800 flex">
                  <div className="bg-red-500 h-full" style={{ width: '51%' }} />
                  <div className="bg-cyan-400 h-full" style={{ width: '49%' }} />
                </div>
              </div>
            </div>
          </div>

          {/* Mini-Sectors Corner Comparison */}
          <div className="bg-zinc-950 p-4 rounded-xl border border-zinc-800">
            <h4 className="text-xs font-black uppercase tracking-wider text-white mb-2 flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 text-orange-400" />
              Corner Delta Advantage (COTA Micro-Sectors)
            </h4>
            <div className="grid grid-cols-4 gap-2 text-center text-xs">
              <div className="bg-zinc-900 p-2 rounded-lg border border-red-500/30">
                <span className="text-[10px] text-zinc-400 block font-mono">T1 (Apex)</span>
                <span className="font-bold text-red-400 font-mono">-0.042s</span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-red-500/30">
                <span className="text-[10px] text-zinc-400 block font-mono">T3-T6 (Esses)</span>
                <span className="font-bold text-red-400 font-mono">-0.089s</span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-cyan-500/30">
                <span className="text-[10px] text-zinc-400 block font-mono">T11-T12 (Straight)</span>
                <span className="font-bold text-cyan-400 font-mono">+0.065s</span>
              </div>
              <div className="bg-zinc-900 p-2 rounded-lg border border-red-500/30">
                <span className="text-[10px] text-zinc-400 block font-mono">T19-T20 (Final)</span>
                <span className="font-bold text-red-400 font-mono">-0.038s</span>
              </div>
            </div>
            <p className="text-[11px] text-zinc-400 mt-3 leading-relaxed">
              <strong className="text-red-400">#{driverA.driver.name_acronym}</strong> genera ventaja clave en las curvas de alta velocidad (Sector 1 Esses) gracias a mayor carga aerodinámica, mientras que <strong className="text-cyan-400">#{driverB.driver.name_acronym}</strong> recupera +0.065s en la recta trasera con menor drag.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
