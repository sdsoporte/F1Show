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

  const progressPercent = totalEvents > 0 ? (currentIndex / (totalEvents - 1)) * 100 : 0;

  return (
    <div className="bg-zinc-900 border-t border-zinc-800 px-4 py-2 sm:py-2.5 shadow-2xl shrink-0 z-30">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        {/* Timeline scrubber */}
        <div className="w-full md:w-1/2 flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-zinc-400 font-mono text-xs whitespace-nowrap min-w-[70px]">
            <Clock className="w-3.5 h-3.5 text-red-500" />
            <span>{formatTime(currentEventTime)}</span>
          </div>

          <div className="relative flex-1 flex items-center">
            <input
              type="range"
              min={0}
              max={Math.max(totalEvents - 1, 0)}
              value={currentIndex}
              onChange={e => onSeek(Number(e.target.value))}
              aria-label="Replay timeline progress"
              className="w-full h-2 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-red-600 focus:outline-none"
            />
          </div>

          <div className="text-zinc-400 font-mono text-xs whitespace-nowrap min-w-[90px] text-right">
            <span>{currentIndex}</span> / <span className="text-zinc-500">{totalEvents}</span>
          </div>
        </div>

        {/* Playback action buttons */}
        <div className="flex items-center gap-2">
          {/* Reset to Start */}
          <button
            onClick={onReset}
            className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
            title="Reset to beginning of session"
          >
            <RotateCcw className="w-4 h-4" />
          </button>

          {/* Step Back */}
          <button
            onClick={onStepBackward}
            disabled={currentIndex <= 0}
            className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 disabled:opacity-40 disabled:hover:bg-zinc-800/80 transition-colors"
            title="Step 1 event backward (Left Arrow)"
          >
            <SkipBack className="w-4 h-4" />
          </button>

          {/* Play / Pause */}
          <button
            onClick={onTogglePlay}
            className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold flex items-center gap-2 shadow-lg shadow-red-600/30 transition-all active:scale-95"
            title="Play / Pause Replay (Spacebar)"
          >
            {isPlaying ? (
              <>
                <Pause className="w-4 h-4 fill-white" />
                <span className="text-xs uppercase tracking-wider">Pause</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span className="text-xs uppercase tracking-wider">Play</span>
              </>
            )}
          </button>

          {/* Step Forward */}
          <button
            onClick={onStepForward}
            disabled={currentIndex >= totalEvents - 1}
            className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 disabled:opacity-40 disabled:hover:bg-zinc-800/80 transition-colors"
            title="Step 1 event forward (Right Arrow)"
          >
            <SkipForward className="w-4 h-4" />
          </button>

          {/* Jump to End */}
          <button
            onClick={onJumpToEnd}
            className="p-2 rounded-lg bg-zinc-800/80 hover:bg-zinc-700 text-zinc-300 transition-colors"
            title="Fast forward to latest event"
          >
            <FastForward className="w-4 h-4" />
          </button>
        </div>

        {/* Speed multiplier selector */}
        <div className="flex items-center gap-1.5 bg-zinc-800/80 border border-zinc-700/60 rounded-lg p-1">
          <Gauge className="w-3.5 h-3.5 text-zinc-400 ml-1.5" />
          <span className="text-[10px] uppercase font-bold text-zinc-400 mr-1 hidden sm:inline">
            Speed
          </span>
          <div className="flex items-center gap-1">
            {SPEED_OPTIONS.map(spd => (
              <button
                key={spd}
                onClick={() => onChangeSpeed(spd)}
                className={`px-2 py-1 rounded text-xs font-mono font-bold transition-all ${
                  playbackSpeed === spd
                    ? 'bg-red-600 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/60'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
