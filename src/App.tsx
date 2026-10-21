import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import {
  BoothLanguage,
  BoothSpeaker,
  DetectedEvent,
  LiveDriverState,
  Turn,
} from './types/f1';
import { getSessionData } from './services/fixtureLoader';
import { collectSessionEvents } from './services/collector';
import { computeSalience } from './services/salience';
import {
  computeProvisionalDriverStandings,
  computeProvisionalTeamStandings,
} from './services/standings';
import {
  announcesCaution,
  determineTurnMode,
  generateScriptedTurn,
} from './services/booth';
import { speechService } from './services/speech';

import { Header } from './components/Header';
import { LiveTimingTower } from './components/LiveTimingTower';
import { CommentaryBoothView } from './components/CommentaryBoothView';
import { SaliencePanel } from './components/SaliencePanel';
import { ChampionshipPanel } from './components/ChampionshipPanel';
import { TacticalPanel } from './components/TacticalPanel';
import { CircuitMap2D } from './components/CircuitMap2D';
import { PlaybackControls } from './components/PlaybackControls';
import { EvidenceModal } from './components/EvidenceModal';
import { SignalRMonitorModal } from './components/SignalRMonitorModal';
import { ThreeCommentatorStudio } from './components/ThreeCommentatorStudio';
import { HeadToHeadTelemetry } from './components/HeadToHeadTelemetry';
import { ObsStudioView } from './components/ObsStudioView';
import { generateGeminiTurn } from './services/booth';
import {
  f1SignalRClient,
  SignalRStatus,
  LiveTelemetryState,
} from './services/signalrClient';

export type DashboardTab = 'studio' | 'master' | 'pitwall' | 'telemetry' | 'map' | 'obs';

export const App: React.FC = () => {
  // Session and configuration state
  const [sessionKey, setSessionKey] = useState<number>(9655);
  const [language, setLanguage] = useState<BoothLanguage>('es-AR');
  const [audioEnabled, setAudioEnabled] = useState<boolean>(false);
  const [soundEffects, setSoundEffects] = useState<boolean>(true);
  const [geminiMode, setGeminiMode] = useState<boolean>(false);

  // F1 SignalR Live state
  const [isSignalRModalOpen, setIsSignalRModalOpen] = useState<boolean>(false);
  const [signalRStatus, setSignalRStatus] = useState<SignalRStatus>(f1SignalRClient.currentStatus);
  const [liveTelemetry, setLiveTelemetry] = useState<LiveTelemetryState>(f1SignalRClient.telemetryState);

  // Subscribe to live SignalR stream
  useEffect(() => {
    const unsubStatus = f1SignalRClient.subscribeStatus((st) => {
      setSignalRStatus({ ...st });
    });
    const unsubTelemetry = f1SignalRClient.subscribeTelemetry((telem) => {
      setLiveTelemetry({ ...telem });
    });
    return () => {
      unsubStatus();
      unsubTelemetry();
    };
  }, []);

  // When user switches to session 9999, auto-connect or start simulation if not yet active
  useEffect(() => {
    if (sessionKey === 9999) {
      if (!signalRStatus.connected && !signalRStatus.connecting) {
        f1SignalRClient.startSimulation();
      }
    }
  }, [sessionKey, signalRStatus.connected, signalRStatus.connecting]);

  // Replay playback state
  const [currentIndex, setCurrentIndex] = useState<number>(25); // Start after initial grid setups
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(2);

  // Inspector and selection state
  const isObsDirect = typeof window !== 'undefined' && window.location.search.includes('obs=true');
  const [dashboardTab, setDashboardTab] = useState<DashboardTab>(isObsDirect ? 'obs' : 'studio');
  const [selectedDriverNumber, setSelectedDriverNumber] = useState<number | null>(null);
  const [inspectedReference, setInspectedReference] = useState<string | null>(null);
  const [rightTab, setRightTab] = useState<'all' | 'stories' | 'standings' | 'tactical' | 'map'>('all');
  const [centerView, setCenterView] = useState<'booth' | 'map'>('booth');
  const [isGeneratingGemini, setIsGeneratingGemini] = useState<boolean>(false);
  const [customAiTurns, setCustomAiTurns] = useState<Turn[]>([]);
  const [isSpeakingState, setIsSpeakingState] = useState<boolean>(false);
  const [currentSpeakingPersona, setCurrentSpeakingPersona] = useState<BoothSpeaker | null>(null);

  // Synchronize speaking state with 3D avatars
  useEffect(() => {
    const unsub = speechService.onSpeakingChange((speaking, speaker) => {
      setIsSpeakingState(speaking);
      setCurrentSpeakingPersona(speaker);
    });
    return unsub;
  }, []);

  // Load session fixture data
  const sessionData = useMemo(() => {
    return getSessionData(sessionKey);
  }, [sessionKey]);

  // Collect all deterministic events once for this session
  const allEvents = useMemo(() => {
    return collectSessionEvents(sessionKey, sessionData.payloads);
  }, [sessionKey, sessionData]);

  // Reset index when session changes
  useEffect(() => {
    setCurrentIndex(Math.min(25, allEvents.length - 1));
    setIsPlaying(false);
  }, [sessionKey, allEvents.length]);

  // Current event prefix for the replay timeline
  const currentEvents = useMemo(() => {
    return allEvents.slice(0, currentIndex + 1);
  }, [allEvents, currentIndex]);

  const latestEvent = currentEvents[currentEvents.length - 1] || null;

  // Window salience analysis
  const salience = useMemo(() => {
    return computeSalience(currentEvents);
  }, [currentEvents]);

  // Derive live driver telemetry and standings state
  const { driversState, currentLapNumber, currentFlag } = useMemo(() => {
    const driversMap = sessionData.driversMap;
    const positionsMap = new Map<number, number>();
    const prevPositionsMap = new Map<number, number>();
    const gridPositionsMap = new Map<number, number>();
    const lastLapsMap = new Map<number, { lapNumber: number; duration: number | null }>();
    const bestLapsMap = new Map<number, number>();
    const stintsMap = new Map<number, any>();
    const pitCountsMap = new Map<number, number>();
    const inPitMap = new Map<number, boolean>();
    let maxLap = 1;
    let activeFlag: { flag: string; message?: string } | null = null;

    // Scan events prefix
    for (const e of currentEvents) {
      if (e.eventType === 'position_change' && e.driverNumber !== null && typeof e.evidence.position === 'number') {
        const driver = e.driverNumber;
        const pos = e.evidence.position;
        if (!gridPositionsMap.has(driver)) {
          gridPositionsMap.set(driver, pos);
        }
        const existing = positionsMap.get(driver);
        if (existing !== undefined) {
          prevPositionsMap.set(driver, existing);
        }
        positionsMap.set(driver, pos);
      } else if (e.eventType === 'lap_completed' && e.driverNumber !== null) {
        const lapNum = e.evidence.lap_number || 1;
        const duration = e.evidence.lap_duration;
        if (lapNum > maxLap) maxLap = lapNum;
        lastLapsMap.set(e.driverNumber, { lapNumber: lapNum, duration });
        if (typeof duration === 'number' && duration > 0) {
          const currentBest = bestLapsMap.get(e.driverNumber);
          if (currentBest === undefined || duration < currentBest) {
            bestLapsMap.set(e.driverNumber, duration);
          }
        }
      } else if (e.eventType === 'stint_start' && e.driverNumber !== null) {
        stintsMap.set(e.driverNumber, e.evidence);
      } else if (e.eventType === 'pit_stop' && e.driverNumber !== null) {
        pitCountsMap.set(e.driverNumber, (pitCountsMap.get(e.driverNumber) || 0) + 1);
        inPitMap.set(e.driverNumber, true);
      } else if (e.eventType === 'race_control') {
        if (e.evidence.flag) {
          activeFlag = {
            flag: String(e.evidence.flag),
            message: e.evidence.message ? String(e.evidence.message) : undefined,
          };
        }
      }
    }

    // Build LiveDriverState array
    const states: LiveDriverState[] = sessionData.drivers.map(d => {
      const pos = positionsMap.get(d.driver_number) ?? 99;
      const prevPos = prevPositionsMap.get(d.driver_number) ?? pos;
      const gridPos = gridPositionsMap.get(d.driver_number) ?? pos;
      const lastLap = lastLapsMap.get(d.driver_number);
      const bestLap = bestLapsMap.get(d.driver_number) ?? null;
      const stint = stintsMap.get(d.driver_number);

      const isFastest = salience.fastestLap !== null && salience.fastestLap.driverNumber === d.driver_number;

      return {
        driverNumber: d.driver_number,
        driver: d,
        position: pos,
        previousPosition: prevPos,
        gridPosition: gridPos,
        positionDelta: gridPos - pos, // positive = gained places
        lastLapNumber: lastLap?.lapNumber ?? 0,
        lastLapTime: lastLap?.duration ?? null,
        bestLapTime: bestLap,
        isFastestLapHolder: isFastest,
        currentStint: stint || null,
        stintLaps: lastLap ? Math.max(lastLap.lapNumber - (stint?.lap_start || 1), 0) : 0,
        currentCompound: stint?.compound || 'MEDIUM',
        pitCount: pitCountsMap.get(d.driver_number) || 0,
        inPitLane: inPitMap.get(d.driver_number) || false,
        gapToLeader: pos === 1 ? 'LEADER' : `+${((pos - 1) * 1.45).toFixed(3)}s`,
        interval: pos === 1 ? '' : `${(1.15 + (pos % 3) * 0.4).toFixed(3)}s`,
        status: 'RUNNING',
      };
    });

    // If on live SignalR stream (9999), merge live telemetry deltas
    if (sessionKey === 9999) {
      if (liveTelemetry.currentLap) {
        maxLap = liveTelemetry.currentLap;
      }
      if (liveTelemetry.trackStatus) {
        const code = liveTelemetry.trackStatus;
        let flagStr = 'GREEN';
        if (code === '2') flagStr = 'YELLOW';
        else if (code === '4') flagStr = 'SAFETY CAR';
        else if (code === '5') flagStr = 'RED';
        else if (code === '6') flagStr = 'VSC';
        activeFlag = {
          flag: flagStr,
          message: liveTelemetry.trackStatusLabel,
        };
      }

      for (const st of states) {
        const live = liveTelemetry.drivers[String(st.driverNumber)];
        if (live) {
          if (live.position) {
            st.previousPosition = st.position;
            st.position = live.position;
          }
          if (live.gapToLeader) st.gapToLeader = live.gapToLeader;
          if (live.interval) st.interval = live.interval;
          if (live.pitCount !== undefined) st.pitCount = live.pitCount;
          if (live.inPit !== undefined) st.inPitLane = live.inPit;
        }
      }
    }

    // Sort running order by current position
    states.sort((a, b) => a.position - b.position);

    return {
      driversState: states,
      currentLapNumber: maxLap,
      currentFlag: activeFlag,
    };
  }, [currentEvents, sessionData, salience, sessionKey, liveTelemetry]);

  // Running order for championship derivation
  const runningOrder = useMemo(() => {
    return driversState.map(d => ({
      driverNumber: d.driverNumber,
      position: d.position,
    }));
  }, [driversState]);

  // Provisional WDC Standings
  const driverStandings = useMemo(() => {
    return computeProvisionalDriverStandings(
      runningOrder,
      sessionData.championshipDrivers,
      sessionData.driversMap,
      salience.fastestLap ? salience.fastestLap.driverNumber : null,
      sessionData.session.year || 2024
    );
  }, [runningOrder, sessionData, salience.fastestLap]);

  // Provisional WCC Standings
  const teamStandings = useMemo(() => {
    return computeProvisionalTeamStandings(
      driverStandings,
      sessionData.championshipTeams
    );
  }, [driverStandings, sessionData]);

  // Generate turns with booth turn-taking rules
  const { turns, currentSpeaker } = useMemo(() => {
    const generatedTurns: Turn[] = [];
    let lastAiredSpeaker: BoothSpeaker = 'lead';
    let nextSpeaker: BoothSpeaker = 'lead';

    // Group lap-1 events for start aggregation
    const lap1Events: DetectedEvent[] = [];
    let startAggregated = false;

    // Map of previous positions for delta calculation
    const prevPosMap = new Map<number, number>();

    for (let i = 0; i < currentEvents.length; i++) {
      const e = currentEvents[i];

      // Track position changes for delta
      if (e.eventType === 'position_change' && e.driverNumber !== null && typeof e.evidence.position === 'number') {
        prevPosMap.set(e.driverNumber, e.evidence.position);
      }

      // Check for Lap 1 start aggregation
      if (e.eventType === 'lap_completed' && e.evidence.lap_number === 1) {
        lap1Events.push(e);
        if (lap1Events.length === 2 && !startAggregated) {
          // Emit aggregated start turn
          startAggregated = true;
          const startRefs = lap1Events.map(ev => `${ev.family}[${ev.recordIndex}].lap_number`);

          let startText = '';
          if (language === 'es-AR') {
            startText = `¡Se apagaron los semáforos en Lusail! Gran largada de toda la grilla de Fórmula 1. ¡Comienza la acción en la curva uno sin incidentes mayores!`;
          } else if (language === 'en') {
            startText = `Lights out and away we go! A clean start across the entire 20-car Formula 1 grid heading into turn one!`;
          } else {
            startText = `¡Comienza el Gran Premio! Salida limpia para los 20 pilotos al apagarse los semáforos.`;
          }

          generatedTurns.push({
            id: `start_agg_${i}`,
            speaker: 'lead',
            text: startText,
            evidence: startRefs,
            eventRef: `laps_start`,
            mode: 'climax',
            createdAt: e.eventTime || new Date().toISOString(),
            outcome: 'AIRED',
          });

          lastAiredSpeaker = 'lead';
          nextSpeaker = 'color';
          continue;
        } else if (lap1Events.length > 2) {
          // Member covered by start
          generatedTurns.push({
            id: `lap1_covered_${i}`,
            speaker: 'lead',
            text: '',
            evidence: [`laps[${e.recordIndex}].lap_number`],
            eventRef: e.eventId,
            mode: 'build',
            createdAt: e.eventTime || new Date().toISOString(),
            outcome: 'COVERED_BY_START',
          });
          continue;
        }
      }

      // Determine speaker:
      // Priority event allows lead to take priority regardless of turn
      const isPriority = announcesCaution(e);
      const speaker: BoothSpeaker = isPriority ? 'lead' : nextSpeaker;

      // Determine mode: build vs climax
      const prevPos = e.driverNumber !== null ? prevPosMap.get(e.driverNumber) : undefined;
      const mode = determineTurnMode(e, prevPos);

      // Driver info
      const driver = e.driverNumber !== null ? sessionData.driversMap.get(e.driverNumber) || null : null;

      // Generate turn
      const turnResult = generateScriptedTurn(
        e,
        speaker,
        mode,
        language,
        driver,
        salience,
        prevPos
      );

      if (turnResult.outcome === 'AIRED') {
        generatedTurns.push({
          id: `turn_${i}_${e.eventId}`,
          speaker,
          text: turnResult.text,
          evidence: turnResult.evidence,
          eventRef: e.eventId,
          mode,
          createdAt: e.eventTime || new Date().toISOString(),
          outcome: 'AIRED',
          driverNumber: e.driverNumber,
        });

        lastAiredSpeaker = speaker;
        nextSpeaker = speaker === 'lead' ? 'color' : 'lead';
      }
    }

    return {
      turns: generatedTurns,
      currentSpeaker: nextSpeaker,
    };
  }, [currentEvents, language, sessionData, salience]);

  // Combined turns (deterministic replay + custom Gemini AI turns + live SignalR race control)
  const allTurns = useMemo(() => {
    const liveTurns: Turn[] = [];
    if (sessionKey === 9999 && liveTelemetry.raceControlMessages.length > 0) {
      liveTelemetry.raceControlMessages.slice(0, 5).forEach((msg, idx) => {
        liveTurns.push({
          id: `live_rc_${msg.utc}_${idx}`,
          speaker: 'lead',
          text: `[DIRECCIÓN DE CARRERA FIA - VUELTA ${msg.lap}]: ${msg.message}`,
          evidence: [`race_control[live].message`],
          eventRef: `rc_live_${idx}`,
          mode: 'climax',
          createdAt: msg.utc,
          outcome: 'AIRED',
          driverNumber: null,
        });
      });
    }
    return [...turns, ...customAiTurns, ...liveTurns];
  }, [turns, customAiTurns, sessionKey, liveTelemetry.raceControlMessages]);

  // Handler to generate a live AI turn using Gemini 3.8 Flash
  const handleGenerateLiveAITurn = useCallback(async () => {
    if (!latestEvent) return;
    setIsGeneratingGemini(true);
    try {
      const isPriority = announcesCaution(latestEvent);
      const speaker: BoothSpeaker = isPriority ? 'lead' : currentSpeaker;
      const prevPos = latestEvent.driverNumber !== null
        ? driversState.find(d => d.driverNumber === latestEvent.driverNumber)?.previousPosition
        : undefined;
      const mode = determineTurnMode(latestEvent, prevPos);
      const driver = latestEvent.driverNumber !== null
        ? sessionData.driversMap.get(latestEvent.driverNumber) || null
        : null;

      const aiResult = await generateGeminiTurn(
        latestEvent,
        speaker,
        mode,
        language,
        driver,
        salience,
        prevPos
      );

      if (aiResult.outcome === 'AIRED') {
        const newTurn: Turn = {
          id: `gemini_${Date.now()}_${latestEvent.eventId}`,
          speaker,
          text: aiResult.text,
          evidence: aiResult.evidence,
          eventRef: latestEvent.eventId,
          mode,
          createdAt: new Date().toISOString(),
          outcome: 'AIRED',
          driverNumber: latestEvent.driverNumber,
        };
        setCustomAiTurns(prev => [...prev, newTurn]);

        if (audioEnabled) {
          speechService.speak(newTurn.text, newTurn.speaker, language, { immediate: true });
        }
      }
    } finally {
      setIsGeneratingGemini(false);
    }
  }, [latestEvent, currentSpeaker, driversState, sessionData, language, salience, audioEnabled]);

  // Audio commentary playback on new turns when enabled
  const lastSpokenTurnId = useRef<string | null>(null);

  useEffect(() => {
    speechService.setEnabled(audioEnabled);
  }, [audioEnabled]);

  useEffect(() => {
    speechService.setSoundEffects(soundEffects);
  }, [soundEffects]);

  useEffect(() => {
    if (audioEnabled && isPlaying && turns.length > 0) {
      const latestTurn = turns[turns.length - 1];
      if (latestTurn.outcome === 'AIRED' && latestTurn.id !== lastSpokenTurnId.current) {
        lastSpokenTurnId.current = latestTurn.id;
        speechService.speak(latestTurn.text, latestTurn.speaker, language, { immediate: false });
      }
    }
  }, [turns, audioEnabled, isPlaying, language]);

  // Playback timer loop
  useEffect(() => {
    if (!isPlaying) return;

    // Interval time depends on playback speed
    const intervalMs = Math.max(100, Math.floor(1000 / playbackSpeed));
    const timer = setInterval(() => {
      setCurrentIndex(prev => {
        if (prev >= allEvents.length - 1) {
          setIsPlaying(false);
          return prev;
        }
        return prev + 1;
      });
    }, intervalMs);

    return () => clearInterval(timer);
  }, [isPlaying, playbackSpeed, allEvents.length]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) {
        return;
      }
      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying(p => !p);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        setCurrentIndex(i => Math.min(allEvents.length - 1, i + 1));
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        setCurrentIndex(i => Math.max(0, i - 1));
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [allEvents.length]);

  // Inspector details for modal
  const inspectedData = useMemo(() => {
    if (!inspectedReference) return null;
    const match = inspectedReference.match(/^(\w+)\[(\d+)\]/);
    if (!match) return null;
    const family = match[1];
    const index = parseInt(match[2], 10);
    const records = (sessionData.payloads as any)[family] || [];
    const record = records[index];
    const timestamp = record?.date || record?.date_start || null;
    return { record, timestamp };
  }, [inspectedReference, sessionData.payloads]);

  const handlePlayTurnAudio = useCallback((turn: Turn) => {
    speechService.setEnabled(true);
    setAudioEnabled(true);
    speechService.speak(turn.text, turn.speaker, language, { immediate: true });
  }, [language]);

  if (isObsDirect) {
    return (
      <div className="w-screen h-screen overflow-hidden bg-transparent">
        <ObsStudioView
          session={sessionData.session}
          driversState={driversState}
          currentLap={currentLapNumber}
          currentTurn={allTurns[allTurns.length - 1] || null}
          activeSpeaker={currentSpeakingPersona}
          isSpeaking={isSpeakingState}
          onSelectDriver={setSelectedDriverNumber}
          selectedDriverNumber={selectedDriverNumber}
        />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100 flex flex-col selection:bg-red-600 selection:text-white">
      {/* Top Header */}
      <Header
        session={sessionData.session}
        selectedSessionKey={sessionKey}
        onSelectSession={setSessionKey}
        language={language}
        onChangeLanguage={setLanguage}
        audioEnabled={audioEnabled}
        onToggleAudio={() => setAudioEnabled(a => !a)}
        soundEffects={soundEffects}
        onToggleSoundEffects={() => setSoundEffects(s => !s)}
        currentFlag={currentFlag}
        totalEvents={allEvents.length}
        currentEventIndex={currentIndex + 1}
        geminiMode={geminiMode}
        onToggleGeminiMode={() => setGeminiMode(g => !g)}
        onOpenSignalRMonitor={() => setIsSignalRModalOpen(true)}
        isSignalRConnected={signalRStatus.connected}
        isSignalRSimulated={signalRStatus.isSimulated}
      />

      {/* Top Dashboard Navigation Switcher */}
      <div className="bg-zinc-900/90 border-b border-zinc-800/80 px-4 py-2 shrink-0 z-30 backdrop-blur-md">
        <div className="max-w-[1750px] mx-auto flex items-center justify-between gap-2 overflow-x-auto">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <button
              onClick={() => setDashboardTab('studio')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'studio'
                  ? 'bg-red-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>🎙️</span>
              <span>Studio 3D & Relatores</span>
            </button>

            <button
              onClick={() => setDashboardTab('master')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'master'
                  ? 'bg-red-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>📺</span>
              <span>Control Central (3 Cols)</span>
            </button>

            <button
              onClick={() => setDashboardTab('pitwall')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'pitwall'
                  ? 'bg-red-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>⏱️</span>
              <span>Muro de Boxes (Pit Wall)</span>
            </button>

            <button
              onClick={() => setDashboardTab('telemetry')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'telemetry'
                  ? 'bg-cyan-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>📈</span>
              <span>Telemetría H2H</span>
            </button>

            <button
              onClick={() => setDashboardTab('map')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'map'
                  ? 'bg-emerald-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>🗺️</span>
              <span>Circuito 2D GPS</span>
            </button>

            <button
              onClick={() => setDashboardTab('obs')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                dashboardTab === 'obs'
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <span>🎥</span>
              <span>OBS Stream Studio</span>
            </button>
          </div>

          <div className="text-[11px] font-mono text-zinc-400 hidden xl:flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>2026 Telemetry Engine Active</span>
          </div>
        </div>
      </div>

      {/* DASHBOARDS CONTAINER */}
      <main className="flex-1 min-h-0 p-2 sm:p-3 max-w-[1750px] w-full mx-auto overflow-hidden">
        {/* ================= DASHBOARD 1: 3D STUDIO & COMMENTATORS ================= */}
        {dashboardTab === 'studio' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 h-full overflow-hidden">
            {/* Left Column: 3D Studio Canvas */}
            <div className="lg:col-span-7 h-full flex flex-col gap-2 overflow-hidden">
              <div className="flex-1 min-h-0 overflow-hidden">
                <ThreeCommentatorStudio
                  activeSpeaker={currentSpeakingPersona}
                  isSpeaking={isSpeakingState}
                  currentTurnQuote={turns[turns.length - 1]?.text}
                />
              </div>

              {/* Quick Race Ticker Bar */}
              <div className="bg-zinc-900 p-2.5 rounded-xl border border-zinc-800 flex items-center justify-between text-xs shrink-0">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white font-mono">P1: {driversState[0]?.driver.full_name}</span>
                  <span className="text-zinc-400 font-mono">({driversState[0]?.driver.team_name})</span>
                </div>
                <div className="flex items-center gap-3 font-mono">
                  <span className="text-yellow-400">Lap {currentLapNumber}</span>
                  <span className="text-zinc-400">Flag: {currentFlag ? currentFlag.flag : 'GREEN'}</span>
                </div>
              </div>
            </div>

            {/* Right Column: Commentary Feed & AI Generator */}
            <div className="lg:col-span-5 h-full overflow-hidden">
              <CommentaryBoothView
                turns={allTurns}
                activeSpeaker={currentSpeaker}
                language={language}
                onInspectEvidence={setInspectedReference}
                onPlayTurnAudio={handlePlayTurnAudio}
                geminiMode={geminiMode}
                onGenerateGeminiTurn={handleGenerateLiveAITurn}
                isGeneratingGemini={isGeneratingGemini}
              />
            </div>
          </div>
        )}

        {/* ================= DASHBOARD 2: MASTER 3-COLUMN CONTROL ================= */}
        {dashboardTab === 'master' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 h-full min-h-0 overflow-hidden">
            {/* Left Column: Live Timing Tower */}
            <div className="lg:col-span-4 xl:col-span-3 h-full min-h-0 overflow-hidden flex flex-col">
              <LiveTimingTower
                driversState={driversState}
                selectedDriverNumber={selectedDriverNumber}
                onSelectDriver={setSelectedDriverNumber}
                fastestLapHolderNumber={salience.fastestLap ? salience.fastestLap.driverNumber : null}
                currentLapNumber={currentLapNumber}
                sessionType={sessionData.session.session_type}
              />
            </div>

            {/* Center Column: Two-Person Commentary Booth or 2D Circuit Tracker */}
            <div className="lg:col-span-8 xl:col-span-5 h-full min-h-0 flex flex-col gap-2 overflow-hidden">
              <div className="flex items-center justify-between bg-zinc-900/90 p-1.5 rounded-lg border border-zinc-800 text-xs shrink-0">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => setCenterView('booth')}
                    className={`py-1 px-3 rounded-md font-bold transition-all ${
                      centerView === 'booth'
                        ? 'bg-red-600 text-white shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    🎙️ Commentary Booth
                  </button>
                  <button
                    onClick={() => setCenterView('map')}
                    className={`py-1 px-3 rounded-md font-bold transition-all ${
                      centerView === 'map'
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    🗺️ 2D Circuit Tracker
                  </button>
                </div>
                <div className="text-[11px] font-mono text-zinc-400 mr-2 hidden sm:block">
                  {centerView === 'booth' ? `${allTurns.filter(t => t.outcome === 'AIRED').length} Aired Turns` : `${sessionData.session.circuit_short_name} Live GPS`}
                </div>
              </div>

              <div className="flex-1 min-h-0 overflow-hidden">
                {centerView === 'booth' ? (
                  <CommentaryBoothView
                    turns={allTurns}
                    activeSpeaker={currentSpeaker}
                    language={language}
                    onInspectEvidence={setInspectedReference}
                    onPlayTurnAudio={handlePlayTurnAudio}
                    geminiMode={geminiMode}
                    onGenerateGeminiTurn={handleGenerateLiveAITurn}
                    isGeneratingGemini={isGeneratingGemini}
                  />
                ) : (
                  <CircuitMap2D
                    session={sessionData.session}
                    driversState={driversState}
                    selectedDriverNumber={selectedDriverNumber}
                    onSelectDriver={setSelectedDriverNumber}
                    currentLap={currentLapNumber}
                    isPlaying={isPlaying}
                    playbackSpeed={playbackSpeed}
                  />
                )}
              </div>
            </div>

            {/* Right Column: Salience, Championship & Tactical */}
            <div className="lg:col-span-12 xl:col-span-4 h-full min-h-0 flex flex-col gap-2 overflow-hidden">
              <div className="flex items-center gap-1 bg-zinc-900 p-1 rounded-lg border border-zinc-800 text-xs shrink-0">
                <button
                  onClick={() => setRightTab('all')}
                  className={`flex-1 py-1 px-1.5 rounded-md font-bold text-[11px] transition-all ${
                    rightTab === 'all' ? 'bg-zinc-800 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Overview
                </button>
                <button
                  onClick={() => setRightTab('stories')}
                  className={`flex-1 py-1 px-1.5 rounded-md font-bold text-[11px] transition-all ${
                    rightTab === 'stories' ? 'bg-red-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Stories
                </button>
                <button
                  onClick={() => setRightTab('standings')}
                  className={`flex-1 py-1 px-1.5 rounded-md font-bold text-[11px] transition-all ${
                    rightTab === 'standings' ? 'bg-red-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Standings
                </button>
                <button
                  onClick={() => setRightTab('tactical')}
                  className={`flex-1 py-1 px-1.5 rounded-md font-bold text-[11px] transition-all ${
                    rightTab === 'tactical' ? 'bg-cyan-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  Tactical
                </button>
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto space-y-3">
                {rightTab === 'all' && (
                  <>
                    <div className="h-[280px]">
                      <SaliencePanel salience={salience} driversMap={sessionData.driversMap} />
                    </div>
                    <div className="h-[280px]">
                      <ChampionshipPanel driverStandings={driverStandings} teamStandings={teamStandings} />
                    </div>
                  </>
                )}
                {rightTab === 'stories' && (
                  <div className="h-full min-h-[400px]">
                    <SaliencePanel salience={salience} driversMap={sessionData.driversMap} />
                  </div>
                )}
                {rightTab === 'standings' && (
                  <div className="h-full min-h-[400px]">
                    <ChampionshipPanel driverStandings={driverStandings} teamStandings={teamStandings} />
                  </div>
                )}
                {rightTab === 'tactical' && (
                  <div className="h-full min-h-[400px]">
                    <TacticalPanel driversState={driversState} currentLap={currentLapNumber} session={sessionData.session} />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ================= DASHBOARD 3: PIT WALL & RACE CONTROL ================= */}
        {dashboardTab === 'pitwall' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 h-full overflow-hidden">
            <div className="lg:col-span-5 h-full overflow-hidden">
              <LiveTimingTower
                driversState={driversState}
                selectedDriverNumber={selectedDriverNumber}
                onSelectDriver={setSelectedDriverNumber}
                fastestLapHolderNumber={salience.fastestLap ? salience.fastestLap.driverNumber : null}
                currentLapNumber={currentLapNumber}
                sessionType={sessionData.session.session_type}
              />
            </div>
            <div className="lg:col-span-7 h-full flex flex-col gap-3 overflow-y-auto">
              <div className="h-[340px]">
                <TacticalPanel driversState={driversState} currentLap={currentLapNumber} session={sessionData.session} />
              </div>
              <div className="h-[280px]">
                <ChampionshipPanel driverStandings={driverStandings} teamStandings={teamStandings} />
              </div>
            </div>
          </div>
        )}

        {/* ================= DASHBOARD 4: TELEMETRY HEAD-TO-HEAD ================= */}
        {dashboardTab === 'telemetry' && (
          <div className="h-full overflow-hidden">
            <HeadToHeadTelemetry
              driversState={driversState}
              selectedDriverNumber={selectedDriverNumber}
              onSelectDriver={setSelectedDriverNumber}
              currentLap={currentLapNumber}
            />
          </div>
        )}

        {/* ================= DASHBOARD 5: 2D CIRCUIT GPS TRACKER ================= */}
        {dashboardTab === 'map' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 h-full min-h-0 overflow-hidden">
            {/* Left Column: Live Timing Tower */}
            <div className="lg:col-span-4 xl:col-span-3 h-full min-h-0 overflow-hidden flex flex-col">
              <LiveTimingTower
                driversState={driversState}
                selectedDriverNumber={selectedDriverNumber}
                onSelectDriver={setSelectedDriverNumber}
                fastestLapHolderNumber={salience.fastestLap ? salience.fastestLap.driverNumber : null}
                currentLapNumber={currentLapNumber}
                sessionType={sessionData.session.session_type}
              />
            </div>

            {/* Right Column: 2D Circuit Tracker */}
            <div className="lg:col-span-8 xl:col-span-9 h-full min-h-0 overflow-hidden flex flex-col">
              <CircuitMap2D
                session={sessionData.session}
                driversState={driversState}
                selectedDriverNumber={selectedDriverNumber}
                onSelectDriver={setSelectedDriverNumber}
                currentLap={currentLapNumber}
                isPlaying={isPlaying}
                playbackSpeed={playbackSpeed}
              />
            </div>
          </div>
        )}

        {/* ================= DASHBOARD 6: OBS STREAMING STUDIO ================= */}
        {dashboardTab === 'obs' && (
          <div className="h-full overflow-hidden">
            <ObsStudioView
              session={sessionData.session}
              driversState={driversState}
              currentLap={currentLapNumber}
              currentTurn={turns[turns.length - 1] || null}
              activeSpeaker={currentSpeakingPersona}
              isSpeaking={isSpeakingState}
              onSelectDriver={setSelectedDriverNumber}
              selectedDriverNumber={selectedDriverNumber}
            />
          </div>
        )}
      </main>

      {/* Sticky Bottom Playback Controls */}
      <PlaybackControls
        isPlaying={isPlaying}
        onTogglePlay={() => setIsPlaying(p => !p)}
        onStepForward={() => setCurrentIndex(i => Math.min(allEvents.length - 1, i + 1))}
        onStepBackward={() => setCurrentIndex(i => Math.max(0, i - 1))}
        onReset={() => setCurrentIndex(0)}
        onJumpToEnd={() => setCurrentIndex(allEvents.length - 1)}
        currentIndex={currentIndex}
        totalEvents={allEvents.length}
        onSeek={setCurrentIndex}
        playbackSpeed={playbackSpeed}
        onChangeSpeed={setPlaybackSpeed}
        currentEventTime={latestEvent?.eventTime ?? null}
      />

      {/* Evidence Provenance Inspector Modal */}
      {inspectedReference && (
        <EvidenceModal
          reference={inspectedReference}
          onClose={() => setInspectedReference(null)}
          rawRecord={inspectedData?.record}
          timestamp={inspectedData?.timestamp ?? null}
        />
      )}

      {/* Formula 1 SignalR Live Hub Diagnostics Modal */}
      <SignalRMonitorModal
        isOpen={isSignalRModalOpen}
        onClose={() => setIsSignalRModalOpen(false)}
        onSelectLiveSession={() => setSessionKey(9999)}
      />
    </div>
  );
};
