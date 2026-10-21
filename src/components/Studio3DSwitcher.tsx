import React, { useState } from 'react';
import { BoothSpeaker } from '../types/f1';
import { ThreeCommentatorStudio } from './ThreeCommentatorStudio';
import { ThreeCommentatorStudioR3F } from './ThreeCommentatorStudioR3F';

export interface Studio3DSwitcherProps {
  activeSpeaker: BoothSpeaker | null;
  isSpeaking: boolean;
  currentTurnQuote?: string;
  onTriggerCheer?: () => void;
}

type StudioMode = 'legacy' | 'r3f';

/**
 * Renders the 3D studio in either the legacy imperative implementation or the
 * R3F one (F17). Both consume the same props; the toggle is the coexistence
 * contract — the legacy file stays untouched while the R3F version matures.
 */
export const Studio3DSwitcher: React.FC<Studio3DSwitcherProps> = (props) => {
  // Default is the legacy studio: the R3F v1 renders below its visual baseline, and the
  // coexistence contract is "never worse by default" — the user flips to R3F to watch it mature.
  const [mode, setMode] = useState<StudioMode>('legacy');

  return (
    <div className="relative h-full w-full">
      {mode === 'r3f' ? <ThreeCommentatorStudioR3F {...props} /> : <ThreeCommentatorStudio {...props} />}
      <div className="absolute left-1/2 top-1.5 z-10 flex -translate-x-1/2 items-center gap-1 rounded-full border border-zinc-700/70 bg-black/60 px-1 py-0.5 backdrop-blur">
        {(
          [
            ['legacy', 'Legacy'],
            ['r3f', 'R3F'],
          ] as const
        ).map(([m, label]) => (
          <button
            key={m}
            onClick={() => setMode(m)}
            className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wide transition ${
              mode === m ? 'bg-zinc-200 text-zinc-900' : 'text-zinc-400 hover:text-zinc-200'
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
};
