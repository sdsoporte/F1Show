import React, { useState } from 'react';
import {
  Trophy,
  Users,
  Award,
  ChevronUp,
  ChevronDown,
  Minus,
} from 'lucide-react';
import {
  ProvisionalDriverStanding,
  ProvisionalTeamStanding,
} from '../types/f1';

interface ChampionshipPanelProps {
  driverStandings: ProvisionalDriverStanding[];
  teamStandings: ProvisionalTeamStanding[];
}

export const ChampionshipPanel: React.FC<ChampionshipPanelProps> = ({
  driverStandings,
  teamStandings,
}) => {
  const [activeTab, setActiveTab] = useState<'drivers' | 'teams'>('drivers');

  const leaderPoints = driverStandings.length > 0 ? driverStandings[0].provisionalTotalPoints : 0;
  const teamLeaderPoints = teamStandings.length > 0 ? teamStandings[0].provisionalTotalPoints : 0;

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full">
      {/* Header and Tab Selector */}
      <div className="bg-zinc-800/80 px-4 py-2.5 border-b border-zinc-700/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Trophy className="w-4 h-4 text-amber-400" />
          <h2 className="font-black text-sm uppercase tracking-wider text-white">
            Provisional Championship
          </h2>
        </div>

        {/* Tab switcher */}
        <div className="flex items-center gap-1 bg-zinc-950 p-0.5 rounded-lg border border-zinc-800 text-xs">
          <button
            onClick={() => setActiveTab('drivers')}
            className={`px-2.5 py-1 rounded-md font-bold transition-all ${
              activeTab === 'drivers'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Drivers (WDC)
          </button>
          <button
            onClick={() => setActiveTab('teams')}
            className={`px-2.5 py-1 rounded-md font-bold transition-all ${
              activeTab === 'teams'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            Constructors (WCC)
          </button>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-y-auto flex-1 font-mono text-xs">
        {activeTab === 'drivers' ? (
          <div>
            {/* Table Column headers */}
            <div className="grid grid-cols-12 px-3 py-1.5 bg-zinc-950/70 text-[10px] font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
              <div className="col-span-1 text-center">Rank</div>
              <div className="col-span-1 text-center">+/-</div>
              <div className="col-span-5 font-sans">Driver</div>
              <div className="col-span-2 text-center">In-Race</div>
              <div className="col-span-3 text-right">Total (Gap)</div>
            </div>

            <div className="divide-y divide-zinc-800/60">
              {driverStandings.map(ds => {
                const rankDelta = ds.startPosition - ds.provisionalRank;
                const gap = leaderPoints - ds.provisionalTotalPoints;

                return (
                  <div
                    key={ds.driverNumber}
                    className="grid grid-cols-12 px-3 py-1.5 items-center hover:bg-zinc-800/40 transition-colors"
                  >
                    <div className="col-span-1 text-center font-black">
                      {ds.provisionalRank}
                    </div>

                    <div className="col-span-1 flex items-center justify-center text-[10px] font-bold">
                      {rankDelta > 0 ? (
                        <span className="text-emerald-400 flex items-center">
                          <ChevronUp className="w-3 h-3 stroke-[3]" />
                          {rankDelta}
                        </span>
                      ) : rankDelta < 0 ? (
                        <span className="text-red-400 flex items-center">
                          <ChevronDown className="w-3 h-3 stroke-[3]" />
                          {Math.abs(rankDelta)}
                        </span>
                      ) : (
                        <span className="text-zinc-600">
                          <Minus className="w-3 h-3" />
                        </span>
                      )}
                    </div>

                    <div className="col-span-5 font-sans pr-1 truncate">
                      <div className="font-bold text-zinc-100 truncate flex items-center gap-1.5">
                        <span>{ds.driver?.broadcast_name || `#${ds.driverNumber}`}</span>
                        {ds.tiedWithCount > 0 && (
                          <span className="text-[9px] bg-zinc-800 text-zinc-400 px-1 rounded font-mono" title={`Tied with ${ds.tiedWithCount} other driver(s)`}>
                            tie
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-zinc-400 truncate">
                        {ds.driver?.team_name || 'Independent'}
                      </div>
                    </div>

                    <div className="col-span-2 text-center">
                      {ds.racePointsEarned > 0 ? (
                        <span className="text-emerald-400 font-bold font-mono">
                          +{ds.racePointsEarned}
                        </span>
                      ) : (
                        <span className="text-zinc-600">0</span>
                      )}
                    </div>

                    <div className="col-span-3 text-right">
                      <span className="font-black text-white">
                        {ds.provisionalTotalPoints}
                      </span>
                      <span className="text-[10px] text-zinc-400 ml-1">
                        {ds.provisionalRank === 1 ? 'PTS' : `(-${gap})`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div>
            {/* Constructors Table */}
            <div className="grid grid-cols-12 px-3 py-1.5 bg-zinc-950/70 text-[10px] font-bold uppercase tracking-wider text-zinc-400 border-b border-zinc-800">
              <div className="col-span-1 text-center">Rank</div>
              <div className="col-span-1 text-center">+/-</div>
              <div className="col-span-5 font-sans">Team</div>
              <div className="col-span-2 text-center">In-Race</div>
              <div className="col-span-3 text-right">Total (Gap)</div>
            </div>

            <div className="divide-y divide-zinc-800/60">
              {teamStandings.map(ts => {
                const rankDelta = ts.startPosition - ts.provisionalRank;
                const gap = teamLeaderPoints - ts.provisionalTotalPoints;

                return (
                  <div
                    key={ts.teamName}
                    className="grid grid-cols-12 px-3 py-1.5 items-center hover:bg-zinc-800/40 transition-colors"
                  >
                    <div className="col-span-1 text-center font-black">
                      {ts.provisionalRank}
                    </div>

                    <div className="col-span-1 flex items-center justify-center text-[10px] font-bold">
                      {rankDelta > 0 ? (
                        <span className="text-emerald-400 flex items-center">
                          <ChevronUp className="w-3 h-3 stroke-[3]" />
                          {rankDelta}
                        </span>
                      ) : rankDelta < 0 ? (
                        <span className="text-red-400 flex items-center">
                          <ChevronDown className="w-3 h-3 stroke-[3]" />
                          {Math.abs(rankDelta)}
                        </span>
                      ) : (
                        <span className="text-zinc-600">
                          <Minus className="w-3 h-3" />
                        </span>
                      )}
                    </div>

                    <div className="col-span-5 font-sans pr-1 flex items-center gap-2 truncate">
                      <div
                        className="w-1.5 h-4 rounded-sm shrink-0"
                        style={{ backgroundColor: `#${ts.teamColour || 'ffffff'}` }}
                      />
                      <span className="font-bold text-zinc-100 truncate">
                        {ts.teamName}
                      </span>
                    </div>

                    <div className="col-span-2 text-center">
                      {ts.racePointsEarned > 0 ? (
                        <span className="text-emerald-400 font-bold font-mono">
                          +{ts.racePointsEarned}
                        </span>
                      ) : (
                        <span className="text-zinc-600">0</span>
                      )}
                    </div>

                    <div className="col-span-3 text-right">
                      <span className="font-black text-white">
                        {ts.provisionalTotalPoints}
                      </span>
                      <span className="text-[10px] text-zinc-400 ml-1">
                        {ts.provisionalRank === 1 ? 'PTS' : `(-${gap})`}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
