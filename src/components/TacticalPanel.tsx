import React from 'react';
import {
  Compass,
  Radio,
  Clock,
  ShieldAlert,
  Fuel,
  ArrowRight,
} from 'lucide-react';
import { LiveDriverState, SessionRecord } from '../types/f1';

interface TacticalPanelProps {
  driversState: LiveDriverState[];
  currentLap: number;
  session: SessionRecord;
}

// Declared stint median lengths based on F06d stint norms
const STINT_MEDIAN_NORMS: Record<string, number> = {
  SOFT: 20,
  MEDIUM: 28,
  HARD: 40,
  INTERMEDIATE: 24,
  WET: 20,
};

export const TacticalPanel: React.FC<TacticalPanelProps> = ({
  driversState,
  currentLap,
  session,
}) => {
  const isQualifying = session.session_type?.toLowerCase().includes('qualifying');

  // Compute pit window projections for each driver
  const pitWindowCandidates = driversState.map(d => {
    const compound = (d.currentCompound || 'MEDIUM').toUpperCase();
    const medianLength = STINT_MEDIAN_NORMS[compound] || 28;
    const stintStart = d.currentStint?.lap_start || 1;
    const projectedStopLap = Math.ceil(stintStart + medianLength);
    const lapsRemainingInStint = projectedStopLap - currentLap;
    const isWindowOpen = currentLap >= projectedStopLap - 3 && currentLap <= projectedStopLap + 3;

    return {
      driver: d.driver,
      position: d.position,
      compound,
      stintLaps: d.stintLaps,
      projectedStopLap,
      lapsRemainingInStint,
      isWindowOpen,
      pitCount: d.pitCount,
    };
  });

  // Identify DRS Battles (Gap < 1.0s between consecutive cars)
  const drsBattles: Array<{ attacker: string; defender: string; gap: number }> = [];
  for (let i = 1; i < driversState.length; i++) {
    const leader = driversState[i - 1];
    const chaser = driversState[i];
    const rawSec = parseFloat(chaser.interval.replace('s', ''));
    if (!isNaN(rawSec) && rawSec > 0 && rawSec < 1.0) {
      drsBattles.push({
        defender: leader.driver.name_acronym,
        attacker: chaser.driver.name_acronym,
        gap: rawSec,
      });
    }
  }

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header */}
      <div className="bg-zinc-800/80 px-4 py-2.5 border-b border-zinc-700/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Compass className="w-4 h-4 text-cyan-400" />
          <h2 className="font-black text-sm uppercase tracking-wider text-white">
            {isQualifying ? 'Qualifying Elimination Cutoffs' : 'Tactical & Pit Windows (F06)'}
          </h2>
        </div>
        <span className="text-[10px] font-mono text-zinc-400">
          Lap {currentLap}
        </span>
      </div>

      <div className="p-4 space-y-4 overflow-y-auto flex-1 text-xs">
        {/* Active DRS Battles Section */}
        {!isQualifying && (
          <div className="p-2.5 rounded-lg bg-zinc-950/60 border border-zinc-800">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase font-bold text-cyan-400 flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
                DRS Train & Interval Battles (&lt; 1.0s)
              </span>
              <span className="text-[10px] font-mono text-zinc-400 font-bold">
                {drsBattles.length} active
              </span>
            </div>

            {drsBattles.length > 0 ? (
              <div className="space-y-1.5">
                {drsBattles.map((b, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between bg-zinc-900/90 p-2 rounded border border-cyan-500/20"
                  >
                    <div className="flex items-center gap-2 font-mono font-bold text-white">
                      <span className="text-emerald-400">{b.attacker}</span>
                      <ArrowRight className="w-3 h-3 text-zinc-500" />
                      <span className="text-zinc-300">{b.defender}</span>
                    </div>
                    <span className="text-cyan-400 font-mono font-black bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                      +{b.gap.toFixed(3)}s
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-zinc-500 italic">No cars currently within 1.0s DRS window</div>
            )}
          </div>
        )}

        {/* Projected Pit Windows Section */}
        {!isQualifying ? (
          <div>
            <div className="text-[10px] uppercase font-bold text-zinc-400 mb-2 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              Pit Window Projections (Norms Ceiling)
            </div>

            <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1 font-mono text-[11px]">
              {pitWindowCandidates.slice(0, 10).map(c => (
                <div
                  key={c.driver.driver_number}
                  className={`p-2 rounded flex items-center justify-between border ${
                    c.isWindowOpen
                      ? 'bg-amber-950/30 border-amber-500/40 text-amber-200'
                      : 'bg-zinc-950/60 border-zinc-800 text-zinc-300'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-white font-sans w-5">
                      P{c.position}
                    </span>
                    <span className="font-sans font-bold text-zinc-100">
                      {c.driver.name_acronym}
                    </span>
                    <span className="text-[10px] text-zinc-400 font-mono">
                      {c.compound} (L{c.stintLaps})
                    </span>
                  </div>

                  <div className="text-right">
                    {c.isWindowOpen ? (
                      <span className="bg-amber-500 text-black px-1.5 py-0.5 rounded text-[10px] font-black uppercase tracking-wider animate-pulse">
                        WINDOW OPEN
                      </span>
                    ) : (
                      <span className="text-[11px] text-zinc-400">
                        Target: Lap {c.projectedStopLap}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          /* Qualifying Elimination Cutoffs */
          <div className="space-y-3">
            <div className="p-3 bg-zinc-950/60 rounded-lg border border-red-500/30">
              <div className="font-bold text-xs text-red-400 mb-1">
                Q1 Elimination Danger Zone (P16 - P20)
              </div>
              <div className="text-zinc-400 text-[11px]">
                5 cars facing knockout at the 18-minute fence. Position classification based on best eligible lap time.
              </div>
            </div>
            <div className="p-3 bg-zinc-950/60 rounded-lg border border-amber-500/30">
              <div className="font-bold text-xs text-amber-400 mb-1">
                Q2 Cutoff Line (P11 - P15)
              </div>
              <div className="text-zinc-400 text-[11px]">
                5 cars eliminated before the final Q3 pole position shootout.
              </div>
            </div>
            <div className="p-3 bg-zinc-950/60 rounded-lg border border-emerald-500/30">
              <div className="font-bold text-xs text-emerald-400 mb-1">
                Q3 Top 10 Shootout (P1 - P10)
              </div>
              <div className="text-zinc-400 text-[11px]">
                12-minute final session deciding the front 5 rows of the Grand Prix grid.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
