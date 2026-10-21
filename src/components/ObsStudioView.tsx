import React, { useState } from 'react';
import {
  Video,
  Monitor,
  Copy,
  Check,
  Maximize2,
  Sliders,
  Layers,
  Sparkles,
  Radio,
  Eye,
  Settings,
  HelpCircle,
} from 'lucide-react';
import { LiveDriverState, SessionRecord, Turn, BoothSpeaker } from '../types/f1';
import { ThreeCommentatorStudio } from './ThreeCommentatorStudio';

interface ObsStudioViewProps {
  session: SessionRecord;
  driversState: LiveDriverState[];
  currentLap: number;
  currentTurn: Turn | null;
  activeSpeaker: BoothSpeaker | null;
  isSpeaking: boolean;
  onSelectDriver: (num: number | null) => void;
  selectedDriverNumber: number | null;
}

export type ObsSceneType = 'broadcast' | 'avatars_pip' | 'battle' | 'standings';

export const ObsStudioView: React.FC<ObsStudioViewProps> = ({
  session,
  driversState,
  currentLap,
  currentTurn,
  activeSpeaker,
  isSpeaking,
  onSelectDriver,
  selectedDriverNumber,
}) => {
  const [activeScene, setActiveScene] = useState<ObsSceneType>('broadcast');
  const [bgMode, setBgMode] = useState<'transparent' | 'chroma_green' | 'dark'>('transparent');
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [isOverlayExpanded, setIsOverlayExpanded] = useState(false);

  // Top 10 drivers for leaderboard overlay
  const top10 = driversState.slice(0, 10);
  const driverA = driversState[0];
  const driverB = driversState[1] || driversState[0];

  const handleCopyObsUrl = () => {
    const currentOrigin = window.location.origin;
    const url = `${currentOrigin}?obs=true&scene=${activeScene}&bg=${bgMode}`;
    navigator.clipboard.writeText(url);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2500);
  };

  const getBgClass = () => {
    if (bgMode === 'chroma_green') return 'bg-[#00FF00] text-black';
    if (bgMode === 'transparent') return 'bg-transparent';
    return 'bg-zinc-950/90 text-white';
  };

  return (
    <div className="bg-zinc-900 rounded-xl border border-zinc-800 shadow-2xl overflow-hidden flex flex-col h-full">
      {/* OBS Control Bar */}
      <div className="bg-zinc-850 px-4 py-3 border-b border-zinc-700/60 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full bg-red-600 animate-pulse" />
          <h2 className="font-black text-sm uppercase tracking-wider text-white flex items-center gap-1.5">
            <Video className="w-4 h-4 text-red-500" />
            OBS Streaming Studio & Overlays
          </h2>
          <span className="text-[11px] font-mono text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800">
            1080p60 Broadcast Engine
          </span>
        </div>

        {/* Scene Switcher Buttons */}
        <div className="flex items-center gap-1 bg-zinc-950 p-1 rounded-lg border border-zinc-700/70">
          <button
            onClick={() => setActiveScene('broadcast')}
            className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
              activeScene === 'broadcast'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Scene 1: Master TV
          </button>
          <button
            onClick={() => setActiveScene('avatars_pip')}
            className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
              activeScene === 'avatars_pip'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Scene 2: 3D Avatars PIP
          </button>
          <button
            onClick={() => setActiveScene('battle')}
            className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
              activeScene === 'battle'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Scene 3: Battle Telemetry
          </button>
          <button
            onClick={() => setActiveScene('standings')}
            className={`px-2.5 py-1 rounded text-xs font-bold transition-all ${
              activeScene === 'standings'
                ? 'bg-red-600 text-white shadow-sm'
                : 'text-zinc-400 hover:text-white'
            }`}
          >
            Scene 4: Standings Card
          </button>
        </div>

        {/* Background Keying & OBS Copy URL */}
        <div className="flex items-center gap-2">
          {/* Chroma Key Selector */}
          <div className="flex items-center gap-1 text-xs bg-zinc-950 p-1 rounded-lg border border-zinc-800">
            <span className="text-[10px] text-zinc-400 px-1 font-mono">BG:</span>
            <button
              onClick={() => setBgMode('transparent')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                bgMode === 'transparent' ? 'bg-zinc-700 text-white' : 'text-zinc-400'
              }`}
              title="Transparent Alpha (Direct OBS Browser Source)"
            >
              Alpha
            </button>
            <button
              onClick={() => setBgMode('chroma_green')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                bgMode === 'chroma_green' ? 'bg-emerald-600 text-white' : 'text-zinc-400'
              }`}
              title="Chroma Key Green #00FF00"
            >
              Chroma Green
            </button>
            <button
              onClick={() => setBgMode('dark')}
              className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                bgMode === 'dark' ? 'bg-zinc-700 text-white' : 'text-zinc-400'
              }`}
              title="Dark Preview"
            >
              Dark
            </button>
          </div>

          {/* Copy Browser Source URL Button */}
          <button
            onClick={handleCopyObsUrl}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white font-bold text-xs shadow-md transition-all cursor-pointer"
            title="Copy URL to paste directly into OBS Browser Source"
          >
            {copiedUrl ? <Check className="w-3.5 h-3.5 text-white" /> : <Copy className="w-3.5 h-3.5" />}
            {copiedUrl ? 'Copied for OBS!' : 'Copy OBS Browser Source URL'}
          </button>
        </div>
      </div>

      {/* OBS Studio Preview Canvas Viewport */}
      <div className="flex-1 relative overflow-hidden bg-zinc-950 flex items-center justify-center p-4">
        {/* Aspect Ratio 16:9 Frame */}
        <div
          className={`relative w-full max-w-5xl aspect-video rounded-xl overflow-hidden border-2 border-zinc-700 shadow-2xl transition-all ${getBgClass()} ${
            isOverlayExpanded ? 'fixed inset-2 z-50 max-w-none aspect-auto' : ''
          }`}
        >
          {/* ================= SCENE 1: MASTER BROADCAST OVERLAY ================= */}
          {activeScene === 'broadcast' && (
            <div className="absolute inset-0 p-4 sm:p-6 flex flex-col justify-between pointer-events-none">
              {/* Top Bar: Lap counter & Session info */}
              <div className="flex items-center justify-between pointer-events-auto">
                <div className="flex items-center gap-2 bg-black/85 backdrop-blur-md px-3 py-1.5 rounded-md border-l-4 border-red-600 border-y border-r border-zinc-800 shadow-lg">
                  <div className="w-2.5 h-2.5 rounded-full bg-red-600 animate-ping" />
                  <span className="text-xs font-black text-white tracking-wider uppercase font-mono">
                    {session.country_name} GP 2026
                  </span>
                  <span className="text-xs font-mono font-bold text-yellow-400 border-l border-zinc-700 pl-2">
                    LAP {currentLap} / {session.session_name}
                  </span>
                </div>

                <div className="bg-black/80 px-2.5 py-1 rounded text-[11px] font-mono text-zinc-300 border border-zinc-700">
                  🔴 LIVE OBS FEED
                </div>
              </div>

              {/* Left Side: F1 TV Official Vertical Timing Tower */}
              <div className="w-48 bg-black/85 backdrop-blur-md rounded-md border border-zinc-800 overflow-hidden shadow-2xl pointer-events-auto mt-2">
                <div className="bg-red-600 px-2.5 py-1 text-[10px] font-black uppercase text-white tracking-wider flex justify-between items-center">
                  <span>LEADERBOARD</span>
                  <span className="text-[9px] font-mono">GAP</span>
                </div>
                <div className="divide-y divide-zinc-800/80 text-[11px] font-mono">
                  {top10.map((d, index) => (
                    <div
                      key={d.driverNumber}
                      className={`px-2 py-1 flex items-center justify-between transition-colors ${
                        selectedDriverNumber === d.driverNumber ? 'bg-zinc-700/60' : 'hover:bg-zinc-800/40'
                      }`}
                    >
                      <div className="flex items-center gap-1.5">
                        <span className="font-bold text-zinc-400 w-3">{index + 1}</span>
                        <div
                          className="w-1 h-3 rounded-full"
                          style={{ backgroundColor: d.driver.team_colour ? `#${d.driver.team_colour}` : '#999' }}
                        />
                        <span className="font-bold text-white">{d.driver.name_acronym}</span>
                      </div>
                      <span className="text-zinc-300 font-mono text-[10px]">
                        {index === 0 ? 'INTERVAL' : d.interval || d.gapToLeader || '+0.000'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Bottom: Broadcast Lower Third with Dynamic Commentary */}
              <div className="max-w-2xl bg-black/90 backdrop-blur-md p-3.5 rounded-lg border-l-4 border-red-600 border-y border-r border-zinc-800 shadow-2xl pointer-events-auto">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <Radio className="w-4 h-4 text-red-500 animate-pulse" />
                    <span className="text-xs font-black uppercase tracking-wider text-red-500 font-mono">
                      F1 LIVE BOOTH • {currentTurn?.speaker === 'lead' ? 'CARLOS (RELATOR)' : 'ALEX (ANALISTA)'}
                    </span>
                  </div>
                  <span className="text-[10px] font-mono text-zinc-400">
                    AI Broadcast Telemetry Grounded
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-zinc-100 font-medium italic">
                  "{currentTurn?.text || 'Monoplazas en pista manteniendo ritmo constante en el Sector 2. Verstappen gestiona la degradación del neumático medio.'}"
                </p>
              </div>
            </div>
          )}

          {/* ================= SCENE 2: 3D AVATARS PIP STUDIO ================= */}
          {activeScene === 'avatars_pip' && (
            <div className="absolute inset-0 flex flex-col justify-between">
              {/* 3D Avatars Studio Canvas */}
              <div className="flex-1 w-full h-full">
                <ThreeCommentatorStudio
                  activeSpeaker={activeSpeaker}
                  isSpeaking={isSpeaking}
                  currentTurnQuote={currentTurn?.text}
                />
              </div>
            </div>
          )}

          {/* ================= SCENE 3: BATTLE TELEMETRY OVERLAY ================= */}
          {activeScene === 'battle' && driverA && driverB && (
            <div className="absolute inset-0 p-6 flex flex-col justify-end pointer-events-none">
              <div className="bg-black/90 backdrop-blur-md rounded-xl p-4 border border-zinc-700/80 shadow-2xl max-w-xl mx-auto w-full pointer-events-auto">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse" />
                    <h4 className="text-xs font-black uppercase tracking-wider text-white">
                      HEAD-TO-HEAD BATTLE FOR P{driverA.position}
                    </h4>
                  </div>
                  <span className="text-xs font-mono font-bold text-yellow-400">
                    DELTA: {driverB.interval || '+0.420s'}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Driver 1 */}
                  <div className="bg-zinc-950 p-3 rounded-lg border border-red-500/40">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm font-black text-white">#{driverA.driverNumber} {driverA.driver.name_acronym}</span>
                      <span className="text-xs font-mono text-zinc-400">P{driverA.position}</span>
                    </div>
                    <div className="text-[11px] font-mono text-zinc-300 space-y-1">
                      <div className="flex justify-between">
                        <span>Speed:</span>
                        <span className="font-bold text-white">331 km/h</span>
                      </div>
                      <div className="flex justify-between">
                        <span>DRS:</span>
                        <span className="font-bold text-emerald-400">ENABLED</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Tyres:</span>
                        <span className="text-yellow-400">{driverA.currentCompound || 'M'} ({driverA.stintLaps || 1}L)</span>
                      </div>
                    </div>
                  </div>

                  {/* Driver 2 */}
                  <div className="bg-zinc-950 p-3 rounded-lg border border-cyan-500/40">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-sm font-black text-white">#{driverB.driverNumber} {driverB.driver.name_acronym}</span>
                      <span className="text-xs font-mono text-zinc-400">P{driverB.position}</span>
                    </div>
                    <div className="text-[11px] font-mono text-zinc-300 space-y-1">
                      <div className="flex justify-between">
                        <span>Speed:</span>
                        <span className="font-bold text-white">328 km/h</span>
                      </div>
                      <div className="flex justify-between">
                        <span>DRS:</span>
                        <span className="font-bold text-zinc-400">IN ZONE (0.4s)</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Tyres:</span>
                        <span className="text-yellow-400">{driverB.currentCompound || 'M'} ({driverB.stintLaps || 1}L)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ================= SCENE 4: STANDINGS CARD ================= */}
          {activeScene === 'standings' && (
            <div className="absolute inset-0 p-6 flex items-center justify-center bg-black/90 pointer-events-auto">
              <div className="max-w-2xl w-full bg-zinc-900 border border-zinc-700 rounded-xl p-5 shadow-2xl">
                <div className="flex items-center justify-between border-b border-zinc-700 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-red-600" />
                    <h3 className="text-base font-black uppercase text-white tracking-wider">
                      {session.circuit_short_name} • CURRENT RUNNING ORDER
                    </h3>
                  </div>
                  <span className="text-xs font-mono text-zinc-400">LAP {currentLap} CLASSIFICATION</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                  {driversState.slice(0, 10).map(d => (
                    <div key={d.driverNumber} className="flex items-center justify-between bg-zinc-950 p-2 rounded border border-zinc-800">
                      <div className="flex items-center gap-2">
                        <span className="text-zinc-500 font-bold w-4">P{d.position}</span>
                        <span className="text-white font-black">{d.driver.name_acronym}</span>
                        <span className="text-[10px] text-zinc-400 truncate max-w-[90px]">{d.driver.team_name}</span>
                      </div>
                      <span className="text-emerald-400">{d.interval ? d.interval : 'LEAD'}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Instructions Accordion for OBS Setup */}
      <div className="bg-zinc-850 p-3 border-t border-zinc-800 text-xs text-zinc-400 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <HelpCircle className="w-4 h-4 text-cyan-400" />
          <span>
            <strong>Cómo usar en OBS Studio:</strong> En OBS agrega una fuente <em>"Browser" (Navegador)</em>, pega la URL copiada, ajusta resolución a <strong>1920x1080</strong> y activa <em>"Shutdown source when not visible"</em>.
          </span>
        </div>
        <button
          onClick={() => setIsOverlayExpanded(e => !e)}
          className="text-white bg-zinc-800 hover:bg-zinc-700 px-3 py-1 rounded text-xs flex items-center gap-1 cursor-pointer transition-colors"
        >
          <Maximize2 className="w-3 h-3" />
          {isOverlayExpanded ? 'Contraer' : 'Expandir Vista Previa'}
        </button>
      </div>
    </div>
  );
};
