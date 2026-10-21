import React from 'react';
import {
  Flag,
  Radio,
  Volume2,
  VolumeX,
  Languages,
  Calendar,
  Layers,
  Sparkles,
} from 'lucide-react';
import { BoothLanguage, SessionRecord } from '../types/f1';
import { PRESET_SESSIONS } from '../services/fixtureLoader';

interface HeaderProps {
  session: SessionRecord;
  selectedSessionKey: number;
  onSelectSession: (key: number) => void;
  language: BoothLanguage;
  onChangeLanguage: (lang: BoothLanguage) => void;
  audioEnabled: boolean;
  onToggleAudio: () => void;
  soundEffects: boolean;
  onToggleSoundEffects: () => void;
  currentFlag: { flag: string; message?: string } | null;
  totalEvents: number;
  currentEventIndex: number;
  geminiMode: boolean;
  onToggleGeminiMode: () => void;
  onOpenSignalRMonitor?: () => void;
  isSignalRConnected?: boolean;
  isSignalRSimulated?: boolean;
}

const LANGUAGE_LABELS: Record<BoothLanguage, { name: string; tag: string; desc: string }> = {
  'es-AR': { name: 'Español (Argentina)', tag: 'es-AR', desc: 'Voseo, boxes, auto, nafta' },
  'es-419': { name: 'Español (Latam)', tag: 'es-419', desc: 'Neutral, tuteo, pits' },
  'es-MX': { name: 'Español (México)', tag: 'es-MX', desc: 'Llantas, pits, auto' },
  'es-ES': { name: 'Español (España)', tag: 'es-ES', desc: 'Coche, neumáticos, boxes' },
  'en': { name: 'English (UK/Intl)', tag: 'en', desc: 'Car, tyres, pit lane' },
};

export const Header: React.FC<HeaderProps> = ({
  session,
  selectedSessionKey,
  onSelectSession,
  language,
  onChangeLanguage,
  audioEnabled,
  onToggleAudio,
  soundEffects,
  onToggleSoundEffects,
  currentFlag,
  totalEvents,
  currentEventIndex,
  geminiMode,
  onToggleGeminiMode,
  onOpenSignalRMonitor,
  isSignalRConnected,
  isSignalRSimulated,
}) => {
  // Flag styling
  const flagStatus = currentFlag ? currentFlag.flag.toUpperCase() : 'GREEN';
  let flagBadgeBg = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
  let flagLabel = 'TRACK CLEAR';

  if (flagStatus.includes('RED')) {
    flagBadgeBg = 'bg-red-500/20 text-red-400 border-red-500/40 animate-pulse';
    flagLabel = 'RED FLAG';
  } else if (flagStatus.includes('SAFETY') || flagStatus.includes('SC')) {
    flagBadgeBg = 'bg-amber-500/20 text-amber-400 border-amber-500/40 animate-pulse-subtle';
    flagLabel = 'SAFETY CAR';
  } else if (flagStatus.includes('VSC')) {
    flagBadgeBg = 'bg-amber-500/20 text-amber-400 border-amber-500/40';
    flagLabel = 'VIRTUAL SAFETY CAR';
  } else if (flagStatus.includes('YELLOW') || flagStatus.includes('DOUBLE')) {
    flagBadgeBg = 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40';
    flagLabel = 'YELLOW FLAG';
  }

  const isLiveStream = selectedSessionKey === 9999 || isSignalRConnected;

  return (
    <header className="border-b border-zinc-800 bg-zinc-900/90 backdrop-blur-md sticky top-0 z-40">
      {/* Top TV Broadcast ticker */}
      <div className="bg-gradient-to-r from-red-700 via-red-600 to-zinc-900 px-4 py-1.5 flex items-center justify-between text-xs font-semibold tracking-wider text-white">
        <div className="flex items-center gap-3">
          <button
            onClick={onOpenSignalRMonitor}
            className="bg-black/60 hover:bg-black/80 px-2.5 py-0.5 rounded text-[11px] font-black uppercase tracking-widest flex items-center gap-1.5 cursor-pointer transition-colors"
            title="Click to open F1 SignalR Live Hub Diagnostics & Controls"
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isLiveStream
                  ? isSignalRSimulated
                    ? 'bg-emerald-400 animate-ping'
                    : 'bg-red-400 animate-ping'
                  : 'bg-zinc-400'
              } inline-block`}
            />
            <span>
              {isLiveStream
                ? isSignalRSimulated
                  ? 'LIVE SIGNALR (SIM)'
                  : 'LIVE SIGNALR (F1)'
                : 'REPLAY FEED'}
            </span>
            <span className="text-[9px] text-zinc-400 font-mono">⚡ HUD</span>
          </button>
          <span className="text-zinc-100 font-bold uppercase tracking-wider hidden sm:inline">
            F1Show Broadcast Booth
          </span>
          <span className="text-zinc-300 font-mono text-[11px] hidden md:inline">
            • {session.session_name} ({session.year}) - {session.circuit_short_name}, {session.country_name}
          </span>
        </div>

        <div className="flex items-center gap-3">
          {/* Track flag indicator */}
          <div className={`px-2.5 py-0.5 rounded border text-[11px] font-bold uppercase flex items-center gap-1.5 ${flagBadgeBg}`}>
            <Flag className="w-3 h-3" />
            <span>{flagLabel}</span>
          </div>

          {/* Event progress */}
          <span className="text-zinc-300 font-mono text-[11px]">
            EVT {currentEventIndex} / {totalEvents}
          </span>
        </div>
      </div>

      {/* Main navigation & controls bar */}
      <div className="px-4 py-3 flex flex-wrap items-center justify-between gap-3">
        {/* Brand & Grand Prix selection */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-9 h-9 rounded bg-red-600 flex items-center justify-center font-black text-xl text-white shadow-lg shadow-red-600/30">
              F1
            </div>
            <div>
              <h1 className="font-black text-lg leading-none tracking-tight text-white flex items-center gap-2">
                F1Show
                <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 bg-zinc-800 text-zinc-300 rounded border border-zinc-700">
                  REPLAY BOOTH
                </span>
              </h1>
              <p className="text-xs text-zinc-400 font-medium">
                Deterministic Evidence-Grounded Commentary
              </p>
            </div>
          </div>

          <div className="h-6 w-px bg-zinc-800 hidden lg:block mx-1" />

          {/* Session Switcher */}
          <div className="flex items-center gap-1.5 bg-zinc-800/80 border border-zinc-700/60 rounded-lg p-1">
            <Calendar className="w-3.5 h-3.5 text-zinc-400 ml-1.5" />
            <select
              value={selectedSessionKey}
              onChange={e => onSelectSession(Number(e.target.value))}
              aria-label="Select Grand Prix Session"
              className="bg-transparent text-xs font-semibold text-zinc-100 pr-2 pl-1 py-1 focus:outline-none cursor-pointer"
            >
              {PRESET_SESSIONS.map(s => (
                <option key={s.key} value={s.key} className="bg-zinc-900 text-zinc-100">
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Right tools: Dialect, Audio TTS, and Gemini Mode */}
        <div className="flex items-center flex-wrap gap-2.5">
          {/* Dialect / Language Selector */}
          <div className="flex items-center gap-1.5 bg-zinc-800/80 border border-zinc-700/60 rounded-lg px-2.5 py-1">
            <Languages className="w-3.5 h-3.5 text-red-400" />
            <div className="flex flex-col">
              <span className="text-[9px] uppercase font-bold text-zinc-400 tracking-wider">
                Audience Dialect
              </span>
              <select
                value={language}
                onChange={e => onChangeLanguage(e.target.value as BoothLanguage)}
                aria-label="Audience Dialect"
                className="bg-transparent text-xs font-bold text-zinc-100 focus:outline-none cursor-pointer pr-1"
              >
                {Object.entries(LANGUAGE_LABELS).map(([code, meta]) => (
                  <option key={code} value={code} className="bg-zinc-900 text-zinc-100">
                    {meta.name} ({meta.tag})
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Commentary Audio Voice (TTS) Toggle */}
          <button
            onClick={onToggleAudio}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
              audioEnabled
                ? 'bg-red-600/20 border-red-500/50 text-red-300 shadow-sm shadow-red-500/20'
                : 'bg-zinc-800/80 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Read out commentary turns aloud with dual commentator voices"
          >
            {audioEnabled ? (
              <>
                <Volume2 className="w-3.5 h-3.5 text-red-400 animate-pulse" />
                <span>Voice: ON</span>
              </>
            ) : (
              <>
                <VolumeX className="w-3.5 h-3.5" />
                <span>Voice: Muted</span>
              </>
            )}
          </button>

          {/* Sound FX Radio Beep */}
          <button
            onClick={onToggleSoundEffects}
            className={`p-1.5 rounded-lg border transition-all text-xs ${
              soundEffects
                ? 'bg-zinc-800 border-zinc-600 text-zinc-200'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500'
            }`}
            title="Toggle radio chime audio cue"
          >
            <Radio className="w-3.5 h-3.5" />
          </button>

          {/* Gemini Mode Toggle */}
          <button
            onClick={onToggleGeminiMode}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
              geminiMode
                ? 'bg-purple-600/20 border-purple-500/60 text-purple-300 shadow-sm shadow-purple-500/20'
                : 'bg-zinc-800/80 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
            }`}
            title="Toggle between deterministic offline replay and live Gemini AI commentary generation"
          >
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>{geminiMode ? 'Gemini 2.5' : 'Deterministic'}</span>
          </button>

          {/* F1 SignalR Live Hub Button */}
          {onOpenSignalRMonitor && (
            <button
              onClick={onOpenSignalRMonitor}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
                isSignalRConnected
                  ? 'bg-red-600/20 border-red-500/60 text-red-300 shadow-sm shadow-red-500/20'
                  : 'bg-zinc-800/80 border-zinc-700/60 text-zinc-400 hover:text-zinc-200'
              }`}
              title="Open F1 SignalR Live Streaming Monitor & Diagnostics"
            >
              <Radio className={`w-3.5 h-3.5 ${isSignalRConnected ? 'text-red-400 animate-pulse' : 'text-zinc-400'}`} />
              <span>SignalR Hub</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
