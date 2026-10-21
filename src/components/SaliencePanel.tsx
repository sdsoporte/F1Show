import React from 'react';
import {
  Trophy,
  Zap,
  Flame,
  ArrowUpRight,
  ArrowDownRight,
  Flag,
  Wrench,
  Activity,
  Award,
} from 'lucide-react';
import { Driver, SalienceWindow } from '../types/f1';

interface SaliencePanelProps {
  salience: SalienceWindow;
  driversMap: Map<number, Driver>;
}

export const SaliencePanel: React.FC<SaliencePanelProps> = ({
  salience,
  driversMap,
}) => {
  const getDriverDisplay = (driverNumber: number) => {
    const d = driversMap.get(driverNumber);
    if (!d) return `#${driverNumber}`;
    return `${d.broadcast_name} (${d.team_name})`;
  };

  const formatLapTime = (time: number) => {
    const mins = Math.floor(time / 60);
    const secs = (time % 60).toFixed(3);
    const padded = secs.length < 6 ? `0${secs}` : secs;
    return `${mins}:${padded}`;
  };

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="bg-zinc-800/80 px-4 py-2.5 border-b border-zinc-700/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Award className="w-4 h-4 text-purple-400" />
          <h2 className="font-black text-sm uppercase tracking-wider text-white">
            Race Stories & Salience
          </h2>
        </div>
        <span className="text-[10px] font-mono text-zinc-400">
          Window Analysis
        </span>
      </div>

      <div className="p-4 space-y-4 overflow-y-auto flex-1 text-xs">
        {/* Fastest Lap Card */}
        <div className="p-3 rounded-lg bg-zinc-950/70 border border-purple-500/30">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] uppercase font-bold text-purple-400 tracking-wider flex items-center gap-1.5">
              <Trophy className="w-3.5 h-3.5 text-purple-400" />
              Fastest Lap (Lap ≥ 2)
            </span>
            {salience.fastestLap && (
              <span className="text-[10px] font-mono font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300">
                {salience.fastestLap.duration.toFixed(3)}s
              </span>
            )}
          </div>

          {salience.fastestLap ? (
            <div>
              <div className="font-black text-sm text-white">
                {getDriverDisplay(salience.fastestLap.driverNumber)}
              </div>
              <div className="text-[11px] text-zinc-400 mt-0.5">
                Clocked on Lap {salience.fastestLap.lapNumber} ({formatLapTime(salience.fastestLap.duration)})
              </div>
            </div>
          ) : (
            <div className="text-zinc-500 italic">No valid flying lap recorded yet</div>
          )}
        </div>

        {/* Gainers & Losers */}
        <div className="grid grid-cols-2 gap-3">
          {/* Biggest Gainers */}
          <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-emerald-500/30">
            <div className="text-[10px] uppercase font-bold text-emerald-400 mb-1.5 flex items-center gap-1">
              <ArrowUpRight className="w-3.5 h-3.5" />
              Biggest Gainer(s)
            </div>
            {salience.biggestGainers.length > 0 ? (
              <div className="space-y-1">
                {salience.biggestGainers.map((g, idx) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="font-bold text-zinc-200 truncate pr-1">
                      {driversMap.get(g.driverNumber)?.name_acronym || `#${g.driverNumber}`}
                    </span>
                    <span className="font-mono text-emerald-400 font-bold whitespace-nowrap">
                      +{g.delta} (P{g.startPos}→P{g.currentPos})
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-zinc-500 italic">No position gain</div>
            )}
          </div>

          {/* Biggest Losers */}
          <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-red-500/30">
            <div className="text-[10px] uppercase font-bold text-red-400 mb-1.5 flex items-center gap-1">
              <ArrowDownRight className="w-3.5 h-3.5" />
              Biggest Loser(s)
            </div>
            {salience.biggestLosers.length > 0 ? (
              <div className="space-y-1">
                {salience.biggestLosers.map((l, idx) => (
                  <div key={idx} className="flex items-center justify-between">
                    <span className="font-bold text-zinc-200 truncate pr-1">
                      {driversMap.get(l.driverNumber)?.name_acronym || `#${l.driverNumber}`}
                    </span>
                    <span className="font-mono text-red-400 font-bold whitespace-nowrap">
                      {l.delta} (P{l.startPos}→P{l.currentPos})
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-zinc-500 italic">No position loss</div>
            )}
          </div>
        </div>

        {/* Busiest Driver */}
        <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] uppercase font-bold text-zinc-400 flex items-center gap-1.5">
              <Flame className="w-3.5 h-3.5 text-amber-500" />
              Busiest Driver
            </span>
            {salience.busiestDriver && (
              <span className="text-[10px] font-mono text-amber-400 font-bold">
                {salience.busiestDriver.changeCount} changes
              </span>
            )}
          </div>
          {salience.busiestDriver ? (
            <div className="font-bold text-zinc-200">
              {getDriverDisplay(salience.busiestDriver.driverNumber)}
            </div>
          ) : (
            <div className="text-zinc-500 italic">No position swaps yet</div>
          )}
        </div>

        {/* Pace Outlier Fences */}
        {salience.medianDuration && (
          <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] uppercase font-bold text-zinc-400 flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-cyan-400" />
                Window Median Pace
              </span>
              <span className="text-[10px] font-mono text-cyan-400 font-bold">
                {salience.medianDuration.toFixed(3)}s
              </span>
            </div>
            <div className="grid grid-cols-2 gap-2 mt-2 text-[11px]">
              <div className="bg-zinc-900 p-1.5 rounded">
                <span className="text-zinc-500 block">Fast Outliers (&lt;0.75x)</span>
                <span className="font-mono font-bold text-emerald-400">
                  {salience.fastOutliers.length} laps
                </span>
              </div>
              <div className="bg-zinc-900 p-1.5 rounded">
                <span className="text-zinc-500 block">Slow Outliers (&gt;1.25x)</span>
                <span className="font-mono font-bold text-amber-400">
                  {salience.slowOutliers.length} laps
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Pit Stops in Window */}
        <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800">
          <div className="text-[10px] uppercase font-bold text-zinc-400 mb-2 flex items-center gap-1.5">
            <Wrench className="w-3.5 h-3.5 text-blue-400" />
            Pit Stops Executed ({salience.pitStops.length})
          </div>
          {salience.pitStops.length > 0 ? (
            <div className="space-y-1.5 max-h-28 overflow-y-auto pr-1 font-mono text-[11px]">
              {salience.pitStops.map((ps, idx) => (
                <div key={idx} className="flex items-center justify-between bg-zinc-900 p-1.5 rounded">
                  <span className="font-sans font-bold text-zinc-200">
                    {driversMap.get(ps.driverNumber)?.broadcast_name || `#${ps.driverNumber}`}
                  </span>
                  <span className="text-zinc-400">
                    Lap {ps.lapNumber} • {ps.stopDuration ? `${ps.stopDuration.toFixed(2)}s` : 'Completed'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-zinc-500 italic">No pit stops in current window</div>
          )}
        </div>

        {/* Active Flags / Race Control Alerts */}
        {salience.activeFlags.length > 0 && (
          <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-amber-500/30">
            <div className="text-[10px] uppercase font-bold text-amber-400 mb-1.5 flex items-center gap-1.5">
              <Flag className="w-3.5 h-3.5 text-amber-400" />
              Race Control Directives ({salience.activeFlags.length})
            </div>
            <div className="space-y-1.5 max-h-24 overflow-y-auto pr-1">
              {salience.activeFlags.slice(-4).map((f, idx) => (
                <div key={idx} className="text-[11px] bg-zinc-900/80 p-1.5 rounded border border-zinc-800">
                  <span className="font-bold text-amber-300 font-mono">[{f.flag}]</span>{' '}
                  <span className="text-zinc-300">{f.message}</span>
                  {f.sector && <span className="text-zinc-500 font-mono ml-1">(Sec {f.sector})</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
