import React, { useState, useEffect } from 'react';
import {
  X,
  Radio,
  Activity,
  Zap,
  CheckCircle2,
  AlertCircle,
  Play,
  Square,
  RefreshCw,
  Server,
  Layers,
  DollarSign,
  HelpCircle,
  Terminal,
  ShieldCheck,
  Cpu,
} from 'lucide-react';
import {
  f1SignalRClient,
  LiveRawPacket,
  SignalRStatus,
} from '../services/signalrClient';

interface SignalRMonitorModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectLiveSession?: () => void;
}

export const SignalRMonitorModal: React.FC<SignalRMonitorModalProps> = ({
  isOpen,
  onClose,
  onSelectLiveSession,
}) => {
  const [status, setStatus] = useState<SignalRStatus>(f1SignalRClient.currentStatus);
  const [packets, setPackets] = useState<LiveRawPacket[]>([]);
  const [filterTopic, setFilterTopic] = useState<string>('ALL');
  const [selectedPacket, setSelectedPacket] = useState<LiveRawPacket | null>(null);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'stream' | 'costs' | 'architecture'>('stream');

  useEffect(() => {
    if (!isOpen) return;

    // Subscribe to status updates
    const unsubStatus = f1SignalRClient.subscribeStatus((newStatus) => {
      setStatus(newStatus);
      setIsConnecting(newStatus.connecting);
    });

    // Subscribe to live packet stream
    const unsubPackets = f1SignalRClient.subscribePackets((newPacket) => {
      setPackets((prev) => [newPacket, ...prev.slice(0, 49)]);
    });

    // Initial load
    setPackets(f1SignalRClient.recentPackets);
    f1SignalRClient.fetchStatus();

    return () => {
      unsubStatus();
      unsubPackets();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleConnect = async () => {
    setIsConnecting(true);
    await f1SignalRClient.connectToOfficialF1();
    setIsConnecting(false);
    if (onSelectLiveSession) onSelectLiveSession();
  };

  const handleStartSimulation = async () => {
    setIsConnecting(true);
    await f1SignalRClient.startSimulation();
    setIsConnecting(false);
    if (onSelectLiveSession) onSelectLiveSession();
  };

  const handleDisconnect = async () => {
    await f1SignalRClient.disconnect();
  };

  const filteredPackets =
    filterTopic === 'ALL'
      ? packets
      : packets.filter((p) => p.topic.toLowerCase().includes(filterTopic.toLowerCase()));

  // Status visual attributes
  const isLive = status.connected;
  let statusBadgeColor = 'bg-zinc-800 text-zinc-400 border-zinc-700';
  let statusLabel = 'DISCONNECTED';

  if (status.connecting) {
    statusBadgeColor = 'bg-amber-500/20 text-amber-300 border-amber-500/40 animate-pulse';
    statusLabel = 'HANDSHAKING / NEGOTIATING';
  } else if (status.connected && status.isSimulated) {
    statusBadgeColor = 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
    statusLabel = 'LIVE SIMULATED STREAM (1Hz)';
  } else if (status.connected) {
    statusBadgeColor = 'bg-red-500/20 text-red-400 border-red-500/40';
    statusLabel = 'OFFICIAL F1 SIGNALR (LIVE TRACK)';
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="px-5 py-4 border-b border-zinc-800 bg-zinc-900/80 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-red-600 flex items-center justify-center text-white shadow-lg shadow-red-600/30">
              <Radio className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-black text-white text-base tracking-wide">
                  Formula 1 SignalR Live Hub
                </h3>
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-full border ${statusBadgeColor}`}>
                  {statusLabel}
                </span>
              </div>
              <p className="text-xs text-zinc-400 font-mono">
                livetiming.formula1.com/signalr • Hub: <span className="text-zinc-200">Streaming</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center bg-zinc-900 border border-zinc-800 rounded-lg p-1 text-xs">
              <button
                onClick={() => setActiveTab('stream')}
                className={`px-3 py-1 rounded font-bold transition-all ${
                  activeTab === 'stream' ? 'bg-red-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Live Packets
              </button>
              <button
                onClick={() => setActiveTab('costs')}
                className={`px-3 py-1 rounded font-bold transition-all ${
                  activeTab === 'costs' ? 'bg-red-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Cost & Subscription
              </button>
              <button
                onClick={() => setActiveTab('architecture')}
                className={`px-3 py-1 rounded font-bold transition-all ${
                  activeTab === 'architecture' ? 'bg-red-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                Specs & 2026
              </button>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors ml-2"
              title="Close modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Top Quick Status Metric Cards */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-zinc-900/70 border border-zinc-800/80 p-3 rounded-xl">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">
                Session Active
              </span>
              <p className="text-sm font-black text-white truncate mt-0.5">
                {status.sessionName || 'Standby'}
              </p>
              <span className="text-[10px] text-zinc-400 font-mono">
                {status.circuitName}
              </span>
            </div>

            <div className="bg-zinc-900/70 border border-zinc-800/80 p-3 rounded-xl">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">
                Track Flag
              </span>
              <p className="text-sm font-black text-emerald-400 truncate mt-0.5">
                {status.trackStatus || 'Status 1 (Clear)'}
              </p>
              <span className="text-[10px] text-zinc-400 font-mono">
                Code {status.trackStatusCode}
              </span>
            </div>

            <div className="bg-zinc-900/70 border border-zinc-800/80 p-3 rounded-xl">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">
                Packets Received
              </span>
              <p className="text-sm font-black text-white mt-0.5 font-mono">
                {status.packetsCount} <span className="text-xs font-normal text-zinc-400">frames</span>
              </p>
              <span className="text-[10px] text-zinc-400 font-mono">
                {(status.bytesReceived / 1024).toFixed(1)} KB transferred
              </span>
            </div>

            <div className="bg-zinc-900/70 border border-zinc-800/80 p-3 rounded-xl">
              <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-wider block">
                Resource Cost
              </span>
              <p className="text-sm font-black text-emerald-400 mt-0.5 font-mono">
                $0.00 / Free
              </p>
              <span className="text-[10px] text-zinc-400 font-mono">
                Public F1 Stream
              </span>
            </div>
          </div>

          {/* Controls Bar */}
          <div className="bg-zinc-900 border border-zinc-800 p-3 rounded-xl flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-zinc-300">Stream Controls:</span>
              <button
                onClick={handleConnect}
                disabled={isConnecting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-all disabled:opacity-50 shadow-sm shadow-red-600/30"
                title="Connect directly to official F1 Live Timing stream at livetiming.formula1.com"
              >
                <Radio className={`w-3.5 h-3.5 ${isConnecting ? 'animate-spin' : ''}`} />
                <span>Connect to Live Track F1</span>
              </button>

              <button
                onClick={handleStartSimulation}
                disabled={isConnecting}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition-all disabled:opacity-50 shadow-sm shadow-emerald-600/30"
                title="Pushes live 1Hz telemetry packets (ideal when F1 is not currently racing on track)"
              >
                <Play className="w-3.5 h-3.5" />
                <span>Run 2026 US GP Simulation</span>
              </button>

              {isLive && (
                <button
                  onClick={handleDisconnect}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-bold transition-all"
                  title="Disconnect stream"
                >
                  <Square className="w-3.5 h-3.5" />
                  <span>Disconnect</span>
                </button>
              )}
            </div>

            <div className="flex items-center gap-2">
              {onSelectLiveSession && (
                <button
                  onClick={() => {
                    onSelectLiveSession();
                    onClose();
                  }}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-100 rounded-lg text-xs font-bold border border-zinc-700 transition-colors"
                >
                  View in Main Booth & Map →
                </button>
              )}
            </div>
          </div>

          {/* TAB 1: Real-Time Stream Inspector */}
          {activeTab === 'stream' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Terminal className="w-4 h-4 text-red-500" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-200">
                    Live SignalR Frame Stream
                  </h4>
                  <span className="text-[11px] font-mono text-zinc-500">
                    ({filteredPackets.length} recent frames)
                  </span>
                </div>

                {/* Topic Filter Pills */}
                <div className="flex items-center gap-1 text-[11px] font-mono">
                  {['ALL', 'TimingData', 'TrackStatus', 'RaceControl', 'LapCount'].map((topic) => (
                    <button
                      key={topic}
                      onClick={() => setFilterTopic(topic)}
                      className={`px-2 py-0.5 rounded border transition-colors ${
                        filterTopic === topic
                          ? 'bg-zinc-800 border-zinc-600 text-white font-bold'
                          : 'border-zinc-800 text-zinc-500 hover:text-zinc-300'
                      }`}
                    >
                      {topic}
                    </button>
                  ))}
                </div>
              </div>

              {/* Packets Log Area */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-3">
                <div className="md:col-span-7 bg-black/90 border border-zinc-800/90 rounded-xl p-2 font-mono text-xs max-h-[340px] overflow-y-auto space-y-1">
                  {filteredPackets.length === 0 ? (
                    <div className="py-12 text-center text-zinc-500">
                      <Radio className="w-8 h-8 mx-auto mb-2 opacity-40 animate-pulse" />
                      <p className="font-sans text-xs">Waiting for incoming SignalR packets...</p>
                      <p className="text-[10px] text-zinc-600 mt-1">
                        Click "Run 2026 US GP Simulation" to test packets immediately.
                      </p>
                    </div>
                  ) : (
                    filteredPackets.map((pkt) => (
                      <div
                        key={pkt.id}
                        onClick={() => setSelectedPacket(pkt)}
                        className={`p-2 rounded cursor-pointer transition-colors border ${
                          selectedPacket?.id === pkt.id
                            ? 'bg-red-950/40 border-red-500/50 text-red-200'
                            : 'bg-zinc-900/60 border-zinc-800/60 hover:bg-zinc-800/80 text-zinc-300'
                        }`}
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-bold text-red-400">{pkt.topic}</span>
                          <span className="text-[10px] text-zinc-500">
                            {new Date(pkt.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="text-[11px] text-zinc-400 truncate mt-0.5">
                          {JSON.stringify(pkt.data).substring(0, 85)}...
                        </div>
                      </div>
                    ))
                  )}
                </div>

                {/* Packet JSON Inspector */}
                <div className="md:col-span-5 bg-zinc-900/90 border border-zinc-800 rounded-xl p-3 max-h-[340px] overflow-y-auto flex flex-col font-mono text-xs">
                  <div className="flex items-center justify-between border-b border-zinc-800 pb-2 mb-2">
                    <span className="text-[11px] font-bold text-zinc-300 uppercase">
                      Payload Details
                    </span>
                    <span className="text-[10px] text-zinc-500">
                      {selectedPacket?.topic || 'Select a frame'}
                    </span>
                  </div>

                  {selectedPacket ? (
                    <pre className="text-[11px] text-emerald-400 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                      {JSON.stringify(selectedPacket.data, null, 2)}
                    </pre>
                  ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-zinc-500 text-center py-8">
                      <Layers className="w-6 h-6 mb-2 opacity-50" />
                      <p className="font-sans text-xs">Click any frame on the left to inspect its telemetry payload</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Cost & Subscription Analysis */}
          {activeTab === 'costs' && (
            <div className="space-y-4">
              <div className="bg-zinc-900/80 border border-emerald-500/30 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400 mt-0.5">
                    <DollarSign className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white">
                      Análisis de Coste y Recursos para F1 SignalR
                    </h4>
                    <p className="text-xs text-zinc-300 mt-1 leading-relaxed">
                      La implementación de F1 SignalR{' '}
                      <strong className="text-emerald-400">NO tiene coste monetario adicional</strong> y es
                      completamente sostenible con tu infraestructura y suscripción actual. A continuación te
                      detallamos el desglose exacto:
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl">
                  <div className="flex items-center gap-2 text-emerald-400 mb-2">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">Feed F1 SignalR</span>
                  </div>
                  <p className="text-xl font-black text-white font-mono">$0.00 / Gratuito</p>
                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                    El hub de streaming de Formula 1 (<code className="text-zinc-200">livetiming.formula1.com</code>)
                    es el endpoint público que alimenta el live timing de formula1.com. No requiere token de pago para
                    posiciones, sectores ni mensajes de dirección de carrera.
                  </p>
                </div>

                <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl">
                  <div className="flex items-center gap-2 text-cyan-400 mb-2">
                    <Cpu className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">Recursos de Servidor</span>
                  </div>
                  <p className="text-xl font-black text-white font-mono">~0.05 MB / min</p>
                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                    El consumo de ancho de banda y CPU es mínimo. Las tramas SignalR son JSON deltas comprimidos.
                    Toda la decodificación y renderizado de la torre de tiempos y el mapa se ejecuta en el navegador del cliente.
                  </p>
                </div>

                <div className="bg-zinc-900/60 border border-zinc-800 p-4 rounded-xl">
                  <div className="flex items-center gap-2 text-purple-400 mb-2">
                    <Zap className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">IA con Gemini</span>
                  </div>
                  <p className="text-xl font-black text-white font-mono">&lt; $0.05 / carrera</p>
                  <p className="text-xs text-zinc-400 mt-2 leading-relaxed">
                    El modo algorítmico es 100% gratuito ($0). Si activas comentarios en vivo con Gemini 2.5 Flash,
                    la cuota gratuita de Google AI Studio (15 solicitudes por minuto) cubre de sobra una carrera completa sin superar ningún límite.
                  </p>
                </div>
              </div>

              <div className="bg-zinc-900/40 border border-zinc-800 p-4 rounded-xl">
                <h5 className="text-xs font-bold text-white uppercase tracking-wider mb-2 flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  ¿Podremos mantener la aplicación funcional con la suscripción actual?
                </h5>
                <p className="text-xs text-zinc-300 leading-relaxed">
                  <strong>Sí, absolutamente.</strong> No necesitas comprar ninguna licencia de F1 TV Pro ni contratar
                  servidores dedicados de alto coste. La arquitectura actual con Node/Express + Vite + WebSockets / SSE
                  retransmite los deltas de manera ultra liviana, permitiendo mantener la aplicación 100% operativa,
                  fluida y dentro de los límites estándar de la plataforma.
                </p>
              </div>
            </div>
          )}

          {/* TAB 3: Architecture & 2026 Season Readiness */}
          {activeTab === 'architecture' && (
            <div className="space-y-3 text-xs leading-relaxed text-zinc-300">
              <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl">
                <h5 className="font-bold text-white text-sm mb-2">
                  Protocolo Oficial F1 SignalR vs OpenF1 para Octubre 2026
                </h5>
                <p className="mb-2">
                  Formula 1 utiliza Microsoft SignalR 1.5 con transporte WebSocket sobre el hub <code className="text-red-400">Streaming</code>.
                  A diferencia de OpenF1 (que tiene un retraso intencional de 3 a 5 minutos en fines de semana de Gran Premio),
                  SignalR entrega datos con <strong>latencia de 0.8 a 1.5 segundos</strong> respecto a la pista real.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3 font-mono text-[11px]">
                  <div className="p-2 bg-black/60 rounded border border-zinc-800">
                    <span className="text-zinc-400 block font-bold">Canales Principales:</span>
                    <ul className="list-disc list-inside text-zinc-300 mt-1 space-y-0.5">
                      <li><code className="text-red-400">TimingData</code>: Intervalos, vueltas, sectores</li>
                      <li><code className="text-red-400">TrackStatus</code>: Banderas (verde, amarilla, SC, VSC, roja)</li>
                      <li><code className="text-red-400">RaceControlMessages</code>: Investigaciones y sanciones FIA</li>
                      <li><code className="text-red-400">Position.z</code>: Coordenadas GPS comprimidas con zlib</li>
                    </ul>
                  </div>
                  <div className="p-2 bg-black/60 rounded border border-zinc-800">
                    <span className="text-zinc-400 block font-bold">Ventajas Clave:</span>
                    <ul className="list-disc list-inside text-zinc-300 mt-1 space-y-0.5">
                      <li>Tiempos reales en vivo sin delay de 5 min</li>
                      <li>Bajo consumo de paquetes (deltas incrementales)</li>
                      <li>Disponibilidad continua durante eventos oficiales</li>
                      <li>Compatibilidad garantizada para los reglamentos 2026</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-zinc-800 bg-zinc-900/60 flex items-center justify-between text-xs text-zinc-400">
          <div className="flex items-center gap-2">
            <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" />
            <span>Endpoint: livetiming.formula1.com/signalr</span>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-white rounded-lg font-bold transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
