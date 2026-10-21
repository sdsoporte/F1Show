import React, { useState, useMemo } from 'react';
import {
  ChevronUp,
  ChevronDown,
  Minus,
  Timer,
  Zap,
  Search,
  Flag,
  Award,
  Filter,
} from 'lucide-react';
import { LiveDriverState } from '../types/f1';

interface LiveTimingTowerProps {
  driversState: LiveDriverState[];
  selectedDriverNumber: number | null;
  onSelectDriver: (driverNumber: number | null) => void;
  fastestLapHolderNumber: number | null;
  currentLapNumber: number;
  sessionType?: string; // e.g. 'Race' | 'Qualifying' | 'Practice'
}

export const LiveTimingTower: React.FC<LiveTimingTowerProps> = ({
  driversState,
  selectedDriverNumber,
  onSelectDriver,
  fastestLapHolderNumber,
  currentLapNumber,
  sessionType = 'Race',
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  // Auto-detect if session is Qualifying or Practice, but allow manual toggle
  const isQualyOrPractice = useMemo(() => {
    const s = sessionType.toLowerCase();
    return s.includes('qual') || s.includes('practice') || s.includes('fp') || s.includes('shootout');
  }, [sessionType]);

  const [timingMode, setTimingMode] = useState<'race' | 'qualy'>(
    isQualyOrPractice ? 'qualy' : 'race'
  );

  const formatLapTime = (time: number | null) => {
    if (time === null || time === undefined) return '-:--.---';
    const mins = Math.floor(time / 60);
    const secs = (time % 60).toFixed(3);
    const paddedSecs = secs.length < 6 ? `0${secs}` : secs;
    return `${mins}:${paddedSecs}`;
  };

  const getTyreBadge = (compound: string, age: number) => {
    const c = (compound || 'M').toUpperCase();
    let bg = 'bg-yellow-500 text-black';
    let letter = 'M';

    if (c.includes('SOFT') || c === 'S') {
      bg = 'bg-red-600 text-white';
      letter = 'S';
    } else if (c.includes('HARD') || c === 'H') {
      bg = 'bg-zinc-100 text-black';
      letter = 'H';
    } else if (c.includes('INTER') || c === 'I') {
      bg = 'bg-green-600 text-white';
      letter = 'I';
    } else if (c.includes('WET') || c === 'W') {
      bg = 'bg-blue-600 text-white';
      letter = 'W';
    }

    return (
      <div className="flex items-center gap-1">
        <span className={`w-4 h-4 rounded-full font-black text-[10px] flex items-center justify-center shadow-sm ${bg}`}>
          {letter}
        </span>
        <span className="text-[10px] text-zinc-400 font-mono">
          L{age}
        </span>
      </div>
    );
  };

  // Best session lap time for Pole / P1 reference
  const poleLapTime = useMemo(() => {
    const validTimes = driversState
      .map(d => d.bestLapTime)
      .filter((t): t is number => typeof t === 'number' && t > 0);
    return validTimes.length > 0 ? Math.min(...validTimes) : null;
  }, [driversState]);

  // Sort drivers depending on mode:
  // In Qualy/Practice, drivers are ranked by best lap time (or position if tied)
  const sortedDrivers = useMemo(() => {
    const list = [...driversState];
    if (timingMode === 'qualy') {
      list.sort((a, b) => {
        const timeA = a.bestLapTime || 9999;
        const timeB = b.bestLapTime || 9999;
        if (timeA !== timeB) return timeA - timeB;
        return a.position - b.position;
      });
    } else {
      list.sort((a, b) => a.position - b.position);
    }
    return list;
  }, [driversState, timingMode]);

  const filteredDrivers = sortedDrivers.filter(d => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      d.driver.full_name.toLowerCase().includes(q) ||
      d.driver.name_acronym.toLowerCase().includes(q) ||
      d.driver.team_name.toLowerCase().includes(q) ||
      d.driverNumber.toString().includes(q)
    );
  });

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full min-h-0">
      {/* Tower Header */}
      <div className="bg-zinc-850 px-3 py-2 border-b border-zinc-700/60 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse" />
          <div>
            <h2 className="font-black text-xs uppercase tracking-wider text-white flex items-center gap-1.5">
              <span>Live Timing Tower</span>
              {timingMode === 'qualy' ? (
                <span className="bg-purple-950 text-purple-300 border border-purple-800 px-1.5 py-0.2 rounded text-[9px] font-bold">
                  QUALY / FP
                </span>
              ) : (
                <span className="bg-zinc-800 text-zinc-300 px-1.5 py-0.2 rounded text-[9px] font-bold">
                  RACE
                </span>
              )}
            </h2>
            <div className="text-[10px] font-mono text-zinc-400">
              {timingMode === 'qualy' ? 'Clasificación / Pruebas Libres' : `Vuelta ${currentLapNumber}`}
            </div>
          </div>
        </div>

        {/* Mode Switcher [Carrera | Qualy] & Search */}
        <div className="flex items-center gap-1.5">
          <div className="flex items-center bg-zinc-950 p-0.5 rounded-lg border border-zinc-700 text-[10px] font-mono">
            <button
              onClick={() => setTimingMode('race')}
              className={`px-2 py-0.5 rounded font-bold transition-all cursor-pointer ${
                timingMode === 'race'
                  ? 'bg-red-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Modo Carrera (Diferencias en pista, última vuelta)"
            >
              Carrera
            </button>
            <button
              onClick={() => setTimingMode('qualy')}
              className={`px-2 py-0.5 rounded font-bold transition-all cursor-pointer ${
                timingMode === 'qualy'
                  ? 'bg-purple-600 text-white shadow-sm'
                  : 'text-zinc-400 hover:text-white'
              }`}
              title="Modo Qualy & Pruebas (Mejor tiempo, delta a Pole, zonas de eliminación)"
            >
              Qualy/FP
            </button>
          </div>

          {/* Quick Search */}
          <div className="relative w-28 sm:w-32">
            <Search className="w-3 h-3 absolute left-2 top-2 text-zinc-400" />
            <input
              type="text"
              placeholder="Buscar..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="w-full bg-zinc-950/70 border border-zinc-700/70 rounded-md pl-6 pr-2 py-0.5 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-red-500"
            />
          </div>
        </div>
      </div>

      {/* Column Headers */}
      <div className="grid grid-cols-12 px-3 py-1.5 bg-zinc-950/80 text-[10px] font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
        <div className="col-span-1 text-center">Pos</div>
        <div className="col-span-1 text-center">+/-</div>
        <div className="col-span-4">Piloto / Equipo</div>
        <div className="col-span-2 text-center">Neum.</div>
        <div className="col-span-2 text-right">
          {timingMode === 'qualy' ? 'A Pole' : 'Gap Líder'}
        </div>
        <div className="col-span-2 text-right">
          {timingMode === 'qualy' ? 'Mejor Vta' : 'Última Vta'}
        </div>
      </div>

      {/* Driver List (Scrollable) with Elimination Cutoff Lines in Qualy */}
      <div className="divide-y divide-zinc-800/60 overflow-y-auto flex-1 min-h-0 font-mono text-xs">
        {filteredDrivers.map((d, index) => {
          const isSelected = selectedDriverNumber === d.driverNumber;
          const isFastest = fastestLapHolderNumber === d.driverNumber;
          const delta = d.positionDelta;
          const rank = index + 1;

          // Qualy delta to pole calculation
          let deltaToPole = '-';
          if (timingMode === 'qualy') {
            if (d.bestLapTime && poleLapTime) {
              const diff = d.bestLapTime - poleLapTime;
              deltaToPole = diff <= 0.001 ? 'POLE' : `+${diff.toFixed(3)}`;
            } else {
              deltaToPole = d.gapToLeader || '-';
            }
          }

          // Qualy elimination boundaries (Q1 cuts after P15, Q2 cuts after P10)
          const isQ2Cutoff = timingMode === 'qualy' && rank === 10;
          const isQ1Cutoff = timingMode === 'qualy' && rank === 15;

          return (
            <React.Fragment key={d.driverNumber}>
              <div
                onClick={() => onSelectDriver(isSelected ? null : d.driverNumber)}
                className={`grid grid-cols-12 px-3 py-1.5 items-center cursor-pointer transition-colors ${
                  isSelected
                    ? 'bg-red-600/15 border-l-4 border-red-500 text-white'
                    : 'hover:bg-zinc-800/50 text-zinc-300'
                } ${
                  timingMode === 'qualy' && rank > 15
                    ? 'bg-red-950/20'
                    : timingMode === 'qualy' && rank > 10
                    ? 'bg-amber-950/15'
                    : ''
                }`}
              >
                {/* Position */}
                <div className="col-span-1 text-center font-black text-sm">
                  {timingMode === 'qualy' ? rank : d.position}
                </div>

                {/* Delta change since grid / phase */}
                <div className="col-span-1 flex items-center justify-center text-[11px] font-bold">
                  {delta > 0 ? (
                    <span className="text-emerald-400 flex items-center">
                      <ChevronUp className="w-3 h-3 stroke-[3]" />
                      {delta}
                    </span>
                  ) : delta < 0 ? (
                    <span className="text-red-400 flex items-center">
                      <ChevronDown className="w-3 h-3 stroke-[3]" />
                      {Math.abs(delta)}
                    </span>
                  ) : (
                    <span className="text-zinc-600">
                      <Minus className="w-3 h-3" />
                    </span>
                  )}
                </div>

                {/* Driver info & Team color */}
                <div className="col-span-4 flex items-center gap-2 overflow-hidden pr-1">
                  <div
                    className="w-1 h-5 rounded-sm shrink-0"
                    style={{ backgroundColor: `#${d.driver.team_colour || 'ffffff'}` }}
                    title={d.driver.team_name}
                  />
                  <div className="truncate">
                    <div className="font-sans font-black text-xs text-white truncate flex items-center gap-1.5">
                      <span>{d.driver.name_acronym}</span>
                      <span className="text-[10px] text-zinc-400 font-mono">#{d.driverNumber}</span>
                      {d.inPitLane && (
                        <span className="bg-amber-500 text-black px-1 rounded text-[8.5px] font-black uppercase tracking-wider animate-pulse">
                          PIT
                        </span>
                      )}
                    </div>
                    <div className="font-sans text-[10px] text-zinc-400 truncate">
                      {d.driver.team_name}
                    </div>
                  </div>
                </div>

                {/* Tyre Compound & Stint Age */}
                <div className="col-span-2 flex justify-center">
                  {getTyreBadge(d.currentCompound, d.stintLaps)}
                </div>

                {/* Gap to Leader / Delta to Pole */}
                <div className="col-span-2 text-right">
                  {timingMode === 'qualy' ? (
                    <div className={`font-bold ${deltaToPole === 'POLE' ? 'text-purple-400 font-black' : 'text-zinc-200'}`}>
                      {deltaToPole}
                    </div>
                  ) : (
                    <>
                      <div className="font-bold text-zinc-200">
                        {d.position === 1 ? 'LEADER' : d.gapToLeader}
                      </div>
                      {d.position > 1 && d.interval && (
                        <div className="text-[10px] text-zinc-400">
                          +{d.interval}
                        </div>
                      )}
                    </>
                  )}
                </div>

                {/* Last Lap / Best Lap Time */}
                <div className="col-span-2 text-right flex items-center justify-end gap-1">
                  {isFastest && (
                    <span className="w-2 h-2 rounded-full bg-purple-500 shadow-sm shadow-purple-500 animate-pulse" title="Récord de vuelta de la sesión" />
                  )}
                  <span
                    className={
                      isFastest || (timingMode === 'qualy' && rank === 1)
                        ? 'text-purple-400 font-black'
                        : timingMode === 'qualy' && d.bestLapTime
                        ? 'text-emerald-400 font-semibold'
                        : 'text-zinc-300'
                    }
                  >
                    {timingMode === 'qualy'
                      ? formatLapTime(d.bestLapTime || d.lastLapTime)
                      : formatLapTime(d.lastLapTime)}
                  </span>
                </div>
              </div>

              {/* Qualy Elimination Threshold Line after P10 (Q2 Drop Zone) */}
              {isQ2Cutoff && (
                <div className="bg-red-950/80 border-y border-red-600/80 px-3 py-0.5 flex items-center justify-between text-[9px] font-bold text-red-300 uppercase tracking-wider">
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    LÍNEA DE CORTE Q2 (TOP 10 PASS)
                  </span>
                  <span className="text-red-400 font-mono">ELIMINACIÓN P11-P15</span>
                </div>
              )}

              {/* Qualy Elimination Threshold Line after P15 (Q1 Drop Zone) */}
              {isQ1Cutoff && (
                <div className="bg-red-950/80 border-y border-red-600/80 px-3 py-0.5 flex items-center justify-between text-[9px] font-bold text-red-300 uppercase tracking-wider">
                  <span className="flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    LÍNEA DE CORTE Q1 (TOP 15 PASS)
                  </span>
                  <span className="text-red-400 font-mono">ELIMINACIÓN P16-P20</span>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Footer Info / Mode Summary */}
      <div className="bg-zinc-950/90 px-3 py-1.5 border-t border-zinc-800 flex items-center justify-between text-[10px] font-mono text-zinc-400">
        <div className="flex items-center gap-2">
          {timingMode === 'qualy' ? (
            <>
              <span className="w-2 h-2 rounded-full bg-purple-500" />
              <span>Púrpura = Pole / Mejor tiempo</span>
            </>
          ) : (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>Verde = Ganancia de puestos</span>
            </>
          )}
        </div>
        <div className="text-zinc-500">
          {timingMode === 'qualy' ? 'Top 10 avanzan a Q3' : `${driversState.length} Pilotos activos`}
        </div>
      </div>
    </div>
  );
};
