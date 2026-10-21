import React from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  FastForward,
  Clock,
  Gauge,
} from 'lucide-react';

interface PlaybackControlsProps {
  isPlaying: boolean;
  onTogglePlay: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  onReset: () => void;
  onJumpToEnd: () => void;
  currentIndex: number;
  totalEvents: number;
  onSeek: (index: number) => void;
  playbackSpeed: number;
  onChangeSpeed: (speed: number) => void;
  currentEventTime: string | null;
}

const SPEED_OPTIONS = [0.5, 1, 2, 5, 10, 20];

export const PlaybackControls: React.FC<PlaybackControlsProps> = ({
  isPlaying,
  onTogglePlay,
  onStepForward,
  onStepBackward,
  onReset,
  onJumpToEnd,
  currentIndex,
  totalEvents,
  onSeek,
  playbackSpeed,
  onChangeSpeed,
  currentEventTime,
}) => {
  const formatTime = (isoString: string | null) => {
    if (!isoString) return '--:--:--';
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    } catch {
      return isoString;
    }
  };

  const progressPercent = totalEvents > 1 ? (currentIndex / (totalEvents - 1)) * 100 : 0;

  return (
    <footer className="bg-zinc-950 border-t border-zinc-800/90 px-3 py-2 sm:px-4 sm:py-2.5 shadow-2xl shrink-0 relative z-40 select-none">
      <div className="max-w-[1750px] mx-auto flex flex-col md:flex-row items-center justify-between gap-2.5 sm:gap-4">
        {/* Timeline scrubber */}
        <div className="w-full md:flex-1 flex items-center gap-2.5 sm:gap-3 min-w-0">
          <div className="flex items-center gap-1.5 text-zinc-300 font-mono text-xs whitespace-nowrap bg-zinc-900 px-2 py-1 rounded border border-zinc-800 shrink-0">
            <Clock className="w-3.5 h-3.5 text-red-500 animate-pulse" />
            <span className="font-semibold">{formatTime(currentEventTime)}</span>
          </div>

          <div className="relative flex-1 flex items-center min-w-0 py-1">
            {/* Custom filled track indicator behind range */}
            <div className="absolute left-0 right-0 h-2 bg-zinc-850 rounded-full overflow-hidden pointer-events-none border border-zinc-750">
              <div
                className="h-full bg-gradient-to-r from-red-700 to-red-500 rounded-full transition-all duration-75"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <input
              type="range"
              min={0}
              max={Math.max(totalEvents - 1, 0)}
              value={currentIndex}
              onChange={e => onSeek(Number(e.target.value))}
              aria-label="Progreso de telemetría de sesión"
              className="w-full h-2 bg-transparent appearance-none cursor-pointer accent-red-500 focus:outline-none relative z-10 opacity-80 hover:opacity-100 transition-opacity"
            />
          </div>

          <div className="text-zinc-400 font-mono text-[11px] whitespace-nowrap text-right bg-zinc-900/80 px-2 py-1 rounded border border-zinc-800 shrink-0">
            <span className="text-white font-bold">{currentIndex + 1}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-zinc-400">{totalEvents}</span>
          </div>
        </div>

        {/* Right Controls Container: Playback Action Buttons & Speed Multiplier */}
        <div className="flex items-center justify-between md:justify-end gap-3 w-full md:w-auto shrink-0">
          {/* Action buttons */}
          <div className="flex items-center gap-1.5">
            {/* Reset to Start */}
            <button
              onClick={onReset}
              className="p-1.5 sm:p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-colors border border-zinc-800 cursor-pointer"
              title="Reiniciar sesión (Inicio)"
            >
              <RotateCcw className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>

            {/* Step Back */}
            <button
              onClick={onStepBackward}
              disabled={currentIndex <= 0}
              className="p-1.5 sm:p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 disabled:opacity-40 disabled:hover:bg-zinc-900 transition-colors border border-zinc-800 cursor-pointer disabled:cursor-not-allowed"
              title="Retroceder 1 evento (Flecha Izquierda)"
            >
              <SkipBack className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>

            {/* Play / Pause */}
            <button
              onClick={onTogglePlay}
              className="px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold flex items-center gap-1.5 sm:gap-2 shadow-lg shadow-red-600/30 transition-all active:scale-95 cursor-pointer"
              title="Reproducir / Pausar Replay (Barra espaciadora)"
            >
              {isPlaying ? (
                <>
                  <Pause className="w-3.5 h-3.5 sm:w-4 sm:h-4 fill-white" />
                  <span className="text-xs uppercase tracking-wider">Pausa</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 sm:w-4 sm:h-4 fill-white" />
                  <span className="text-xs uppercase tracking-wider">Play</span>
                </>
              )}
            </button>

            {/* Step Forward */}
            <button
              onClick={onStepForward}
              disabled={currentIndex >= totalEvents - 1}
              className="p-1.5 sm:p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 disabled:opacity-40 disabled:hover:bg-zinc-900 transition-colors border border-zinc-800 cursor-pointer disabled:cursor-not-allowed"
              title="Avanzar 1 evento (Flecha Derecha)"
            >
              <SkipForward className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>

            {/* Jump to End */}
            <button
              onClick={onJumpToEnd}
              className="p-1.5 sm:p-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-zinc-300 hover:text-white transition-colors border border-zinc-800 cursor-pointer"
              title="Avanzar al último evento de la sesión"
            >
              <FastForward className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>
          </div>

          {/* Speed multiplier selector */}
          <div className="flex items-center gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-0.5 sm:p-1">
            <Gauge className="w-3.5 h-3.5 text-zinc-400 ml-1" />
            <span className="text-[10px] uppercase font-bold text-zinc-400 mr-1 hidden sm:inline">
              Vel.
            </span>
            <div className="flex items-center gap-0.5">
              {SPEED_OPTIONS.map(spd => (
                <button
                  key={spd}
                  onClick={() => onChangeSpeed(spd)}
                  className={`px-1.5 py-0.5 sm:px-2 sm:py-1 rounded text-[11px] font-mono font-bold transition-all cursor-pointer ${
                    playbackSpeed === spd
                      ? 'bg-red-600 text-white shadow-sm'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                  }`}
                >
                  {spd}x
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};
