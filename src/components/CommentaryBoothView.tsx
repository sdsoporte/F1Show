import React, { useEffect, useRef } from 'react';
import {
  Mic,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Volume2,
  Copy,
  Download,
  Flame,
  TrendingUp,
  Sparkles,
} from 'lucide-react';
import { BoothLanguage, Turn } from '../types/f1';
import { DIALECT_VOCABULARY } from '../services/booth';
import { speechService } from '../services/speech';

interface CommentaryBoothViewProps {
  turns: Turn[];
  activeSpeaker: 'lead' | 'color';
  language: BoothLanguage;
  onInspectEvidence: (reference: string) => void;
  onPlayTurnAudio: (turn: Turn) => void;
  geminiMode: boolean;
  onGenerateGeminiTurn?: () => void;
  isGeneratingGemini?: boolean;
}

export const CommentaryBoothView: React.FC<CommentaryBoothViewProps> = ({
  turns,
  activeSpeaker,
  language,
  onInspectEvidence,
  onPlayTurnAudio,
  geminiMode,
  onGenerateGeminiTurn,
  isGeneratingGemini = false,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const vocab = DIALECT_VOCABULARY[language] || DIALECT_VOCABULARY['es-AR'];

  // Auto-scroll to bottom on new turn
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [turns.length]);

  const copyTranscript = () => {
    const text = turns
      .filter(t => t.outcome === 'AIRED')
      .map(t => `[${t.speaker.toUpperCase()} - ${t.mode.toUpperCase()}] ${t.text} (Evidence: ${t.evidence.join(', ')})`)
      .join('\n\n');
    navigator.clipboard.writeText(text);
  };

  const downloadTranscript = () => {
    const blob = new Blob([JSON.stringify(turns, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `f1show-transcript-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const airedTurns = turns.filter(t => t.outcome === 'AIRED');

  return (
    <div className="bg-zinc-900/90 rounded-xl border border-zinc-800 shadow-xl overflow-hidden flex flex-col h-full">
      {/* Booth Header & Active Speaker Seats */}
      <div className="bg-zinc-800/80 px-4 py-3 border-b border-zinc-700/60">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Mic className="w-4 h-4 text-red-500" />
            <h2 className="font-black text-sm uppercase tracking-wider text-white">
              Two-Person Commentary Booth
            </h2>
            {geminiMode ? (
              <span className="text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/40 px-2 py-0.5 rounded-full font-bold flex items-center gap-1 animate-pulse">
                <Sparkles className="w-2.5 h-2.5" />
                Gemini 3.8 Flash
              </span>
            ) : (
              <span className="text-[10px] bg-zinc-700/60 text-zinc-300 border border-zinc-600/60 px-2 py-0.5 rounded-full font-bold">
                Deterministic Engine
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5">
            {geminiMode && onGenerateGeminiTurn && (
              <button
                onClick={onGenerateGeminiTurn}
                disabled={isGeneratingGemini}
                className="px-2.5 py-1 rounded bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white font-bold text-[11px] flex items-center gap-1 shadow-sm transition-all"
                title="Generate next live turn using Gemini 3.8 Flash"
              >
                <Sparkles className="w-3 h-3" />
                <span>{isGeneratingGemini ? 'Calling AI...' : 'Gen Turn (AI)'}</span>
              </button>
            )}

            <button
              onClick={copyTranscript}
              className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Copy transcript text to clipboard"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={downloadTranscript}
              className="p-1.5 rounded hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
              title="Download JSON transcript"
            >
              <Download className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Dual Commentator Seats */}
        <div className="grid grid-cols-2 gap-3">
          {/* Seat 1: Lead Announcer */}
          <div
            className={`p-2.5 rounded-lg border transition-all ${
              activeSpeaker === 'lead'
                ? 'bg-red-950/40 border-red-500/60 shadow-md shadow-red-500/10'
                : 'bg-zinc-900/60 border-zinc-800'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center font-black text-xs ${
                    activeSpeaker === 'lead'
                      ? 'bg-red-600 text-white shadow-sm shadow-red-600/50 ring-2 ring-red-400/30'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  PB
                </div>
                <div>
                  <div className="font-bold text-xs text-white flex items-center gap-1.5">
                    Carlos (Relatos)
                    {activeSpeaker === 'lead' && (
                      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-ping" />
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-400">
                    Play-by-Play • {vocab.leadStyle}
                  </div>
                </div>
              </div>

              {/* Voice Test Button */}
              <button
                onClick={() => {
                  speechService.setEnabled(true);
                  speechService.speak(
                    '¡Bienvenidos al Gran Premio! Carlos en los relatos de la Fórmula 1.',
                    'lead',
                    language
                  );
                }}
                className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer border border-zinc-700/60 shadow-sm"
                title="Probar audio de voz de Carlos (Relatos)"
              >
                <Volume2 className="w-3 h-3 text-red-400" />
                <span>Probar</span>
              </button>
            </div>
          </div>

          {/* Seat 2: Color Analyst */}
          <div
            className={`p-2.5 rounded-lg border transition-all ${
              activeSpeaker === 'color'
                ? 'bg-cyan-950/40 border-cyan-500/60 shadow-md shadow-cyan-500/10'
                : 'bg-zinc-900/60 border-zinc-800'
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center font-black text-xs ${
                    activeSpeaker === 'color'
                      ? 'bg-cyan-600 text-white shadow-sm shadow-cyan-600/50 ring-2 ring-cyan-400/30'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}
                >
                  CA
                </div>
                <div>
                  <div className="font-bold text-xs text-white flex items-center gap-1.5">
                    Alex (Telemetría)
                    {activeSpeaker === 'color' && (
                      <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-ping" />
                    )}
                  </div>
                  <div className="text-[10px] text-zinc-400">
                    Análisis Técnico • {vocab.colorStyle}
                  </div>
                </div>
              </div>

              {/* Voice Test Button */}
              <button
                onClick={() => {
                  speechService.setEnabled(true);
                  speechService.speak(
                    'Alex analizando la telemetría, el modo override y los neumáticos.',
                    'color',
                    language
                  );
                }}
                className="px-2 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-[10px] font-bold flex items-center gap-1 transition-all cursor-pointer border border-zinc-700/60 shadow-sm"
                title="Probar audio de voz de Alex (Telemetría)"
              >
                <Volume2 className="w-3 h-3 text-cyan-400" />
                <span>Probar</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Transcript Feed */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 space-y-3.5 bg-zinc-950/40"
      >
        {airedTurns.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center p-6 text-zinc-500">
            <Activity className="w-8 h-8 mb-2 opacity-50" />
            <p className="text-sm font-semibold">Waiting for race events...</p>
            <p className="text-xs text-zinc-600 max-w-xs mt-1">
              Press Play or Step Forward in the playback controls below to start the commentary stream.
            </p>
          </div>
        ) : (
          airedTurns.map(turn => {
            const isLead = turn.speaker === 'lead';
            const isClimax = turn.mode === 'climax';

            return (
              <div
                key={turn.id}
                className={`p-3 rounded-xl border transition-all ${
                  isLead
                    ? 'bg-zinc-900/90 border-red-500/30 mr-4'
                    : 'bg-zinc-900/90 border-cyan-500/30 ml-4'
                }`}
              >
                {/* Meta header: Speaker, Mode, Time */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[10px] font-black uppercase px-2 py-0.5 rounded tracking-wider ${
                        isLead
                          ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                          : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                      }`}
                    >
                      {isLead ? 'Lead Announcer' : 'Color Analyst'}
                    </span>

                    <span
                      className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded flex items-center gap-1 ${
                        isClimax
                          ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                          : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      {isClimax ? (
                        <>
                          <Flame className="w-2.5 h-2.5 text-amber-400" />
                          CLIMAX
                        </>
                      ) : (
                        <>
                          <TrendingUp className="w-2.5 h-2.5 text-zinc-400" />
                          BUILD
                        </>
                      )}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onPlayTurnAudio(turn)}
                      className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors"
                      title="Play audio for this turn"
                    >
                      <Volume2 className="w-3.5 h-3.5" />
                    </button>
                    <span className="text-[10px] font-mono text-zinc-500">
                      {new Date(turn.createdAt).toLocaleTimeString([], { hour12: false })}
                    </span>
                  </div>
                </div>

                {/* Commentary Prose */}
                <p className="text-sm text-zinc-100 font-medium leading-relaxed">
                  {turn.text}
                </p>

                {/* Grounded Evidence Citation Badges */}
                {turn.evidence && turn.evidence.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-zinc-800/80 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] text-zinc-400 uppercase font-mono font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                      Grounded Evidence:
                    </span>
                    {turn.evidence.map(ref => (
                      <button
                        key={ref}
                        onClick={() => onInspectEvidence(ref)}
                        className="text-[10px] font-mono bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white px-2 py-0.5 rounded border border-zinc-700 transition-colors flex items-center gap-1"
                        title="Click to inspect exact raw OpenF1 record and provenance"
                      >
                        <span>{ref}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
