export interface SignalRStatus {
  connected: boolean;
  connecting: boolean;
  isSimulated: boolean;
  lastMessageTime: string | null;
  sessionName: string | null;
  circuitName: string;
  trackStatus: string | null;
  trackStatusCode: string;
  driversCount: number;
  packetsCount: number;
  bytesReceived: number;
  error: string | null;
  hub: string;
  endpoint: string;
}

export interface LiveRawPacket {
  id: string;
  topic: string;
  data: any;
  timestamp: string;
}

export interface LiveTelemetryState {
  currentLap: number;
  totalLaps: number;
  trackStatus: string;
  trackStatusLabel: string;
  sessionName: string;
  drivers: Record<
    string,
    {
      position: number;
      gapToLeader: string;
      interval: string;
      lastLapTime: string;
      bestLapTime: string;
      pitCount: number;
      sectors?: Array<{ value: string; previousValue?: string }>;
      inPit?: boolean;
    }
  >;
  raceControlMessages: Array<{
    utc: string;
    lap: number;
    message: string;
    flag?: string;
    category?: string;
  }>;
}

type StatusCallback = (status: SignalRStatus) => void;
type PacketCallback = (packet: LiveRawPacket) => void;
type TelemetryCallback = (telemetry: LiveTelemetryState) => void;

class F1SignalRClientService {
  private eventSource: EventSource | null = null;
  private statusListeners: Set<StatusCallback> = new Set();
  private packetListeners: Set<PacketCallback> = new Set();
  private telemetryListeners: Set<TelemetryCallback> = new Set();

  public recentPackets: LiveRawPacket[] = [];
  public currentStatus: SignalRStatus = {
    connected: false,
    connecting: false,
    isSimulated: false,
    lastMessageTime: null,
    sessionName: 'Official F1 Live Hub',
    circuitName: 'Austin (COTA)',
    trackStatus: 'Track Clear (Green)',
    trackStatusCode: '1',
    driversCount: 20,
    packetsCount: 0,
    bytesReceived: 0,
    error: null,
    hub: 'Streaming',
    endpoint: 'https://livetiming.formula1.com/signalr',
  };

  public telemetryState: LiveTelemetryState = {
    currentLap: 1,
    totalLaps: 56,
    trackStatus: '1',
    trackStatusLabel: 'Track Clear (Green)',
    sessionName: 'F1 Live Timing',
    drivers: {},
    raceControlMessages: [],
  };

  constructor() {
    // Start listening to SSE stream on initialization
    this.initStream();
  }

  public initStream() {
    if (typeof window === 'undefined') return;
    if (this.eventSource) {
      this.eventSource.close();
    }

    try {
      this.eventSource = new EventSource('/api/f1-live/stream');

      this.eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          this.handleIncomingStream(payload);
        } catch {
          // Ignore parse errors on keepalive ping
        }
      };

      this.eventSource.onerror = () => {
        // SSE handles reconnection automatically
      };
    } catch {
      // EventSource fallback
    }

    // Initial status fetch
    this.fetchStatus();
  }

  private handleIncomingStream(payload: any) {
    if (payload.type === 'snapshot') {
      if (payload.status) {
        this.currentStatus = { ...this.currentStatus, ...payload.status };
        this.notifyStatus();
      }
      if (payload.timingData) {
        this.processTimingData(payload.timingData);
      }
      if (payload.trackStatus) {
        this.telemetryState.trackStatus = payload.trackStatus;
      }
    } else if (payload.type === 'update') {
      const packet: LiveRawPacket = {
        id: `pkt_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
        topic: payload.topic,
        data: payload.data,
        timestamp: payload.timestamp || new Date().toISOString(),
      };

      // Add to rolling packet buffer (keep last 60 packets)
      this.recentPackets.unshift(packet);
      if (this.recentPackets.length > 60) {
        this.recentPackets.pop();
      }

      this.currentStatus.packetsCount++;
      this.currentStatus.lastMessageTime = packet.timestamp;
      this.notifyPacket(packet);

      // Process specific F1 SignalR topics
      if (payload.topic === 'TimingData') {
        this.processTimingData(payload.data?.Lines || payload.data);
      } else if (payload.topic === 'TrackStatus') {
        const code = String(payload.data?.Status || payload.data?.status || '1');
        this.telemetryState.trackStatus = code;
        this.currentStatus.trackStatusCode = code;
        this.currentStatus.trackStatus = this.getTrackStatusLabel(code);
        this.notifyTelemetry();
        this.notifyStatus();
      } else if (payload.topic === 'LapCount') {
        if (payload.data?.CurrentLap) {
          this.telemetryState.currentLap = Number(payload.data.CurrentLap);
        }
        if (payload.data?.TotalLaps) {
          this.telemetryState.totalLaps = Number(payload.data.TotalLaps);
        }
        this.notifyTelemetry();
      } else if (payload.topic === 'RaceControlMessages') {
        const msgs = Array.isArray(payload.data) ? payload.data : payload.data?.Messages || [];
        for (const m of msgs) {
          this.telemetryState.raceControlMessages.unshift({
            utc: m.Utc || new Date().toISOString(),
            lap: m.Lap || this.telemetryState.currentLap,
            message: m.Message || '',
            flag: m.Flag,
            category: m.Category,
          });
        }
        if (this.telemetryState.raceControlMessages.length > 25) {
          this.telemetryState.raceControlMessages.length = 25;
        }
        this.notifyTelemetry();
      }
    }
  }

  private processTimingData(lines: any) {
    if (!lines) return;
    for (const [driverNum, line] of Object.entries<any>(lines)) {
      if (!this.telemetryState.drivers[driverNum]) {
        this.telemetryState.drivers[driverNum] = {
          position: Number(line.Position || line.Line || 99),
          gapToLeader: line.GapToLeader || '',
          interval: line.IntervalToPositionAhead?.Value || '',
          lastLapTime: line.LastLapTime?.Value || '',
          bestLapTime: line.BestLapTime?.Value || '',
          pitCount: Number(line.NumberOfPitStops || 0),
          inPit: Boolean(line.InPit),
        };
      } else {
        const d = this.telemetryState.drivers[driverNum];
        if (line.Position) d.position = Number(line.Position);
        if (line.GapToLeader !== undefined) d.gapToLeader = line.GapToLeader;
        if (line.IntervalToPositionAhead?.Value !== undefined) d.interval = line.IntervalToPositionAhead.Value;
        if (line.LastLapTime?.Value) d.lastLapTime = line.LastLapTime.Value;
        if (line.BestLapTime?.Value) d.bestLapTime = line.BestLapTime.Value;
        if (line.NumberOfPitStops !== undefined) d.pitCount = Number(line.NumberOfPitStops);
        if (line.InPit !== undefined) d.inPit = Boolean(line.InPit);
      }
    }
    this.notifyTelemetry();
  }

  private getTrackStatusLabel(code: string): string {
    switch (code) {
      case '1': return 'Track Clear (Green)';
      case '2': return 'Yellow Flag';
      case '4': return 'Safety Car Deployed';
      case '5': return 'Red Flag (Session Suspended)';
      case '6': return 'Virtual Safety Car (VSC)';
      case '7': return 'VSC Ending';
      default: return `Status ${code}`;
    }
  }

  public async fetchStatus(): Promise<SignalRStatus> {
    try {
      const res = await fetch('/api/f1-live/status');
      if (res.ok) {
        const data = await res.json();
        this.currentStatus = { ...this.currentStatus, ...data };
        this.notifyStatus();
      }
    } catch {
      // Offline fallback
    }
    return this.currentStatus;
  }

  public async connectToOfficialF1(): Promise<SignalRStatus> {
    try {
      const res = await fetch('/api/f1-live/connect', { method: 'POST' });
      const data = await res.json();
      if (data.status) {
        this.currentStatus = { ...this.currentStatus, ...data.status };
        this.notifyStatus();
      }
    } catch (e: any) {
      this.currentStatus.error = e.message;
      this.notifyStatus();
    }
    return this.currentStatus;
  }

  public async disconnect(): Promise<SignalRStatus> {
    try {
      const res = await fetch('/api/f1-live/disconnect', { method: 'POST' });
      const data = await res.json();
      if (data.status) {
        this.currentStatus = { ...this.currentStatus, ...data.status };
        this.notifyStatus();
      }
    } catch {
      // ignore
    }
    return this.currentStatus;
  }

  public async startSimulation(): Promise<SignalRStatus> {
    try {
      const res = await fetch('/api/f1-live/simulate', { method: 'POST' });
      const data = await res.json();
      if (data.status) {
        this.currentStatus = { ...this.currentStatus, ...data.status };
        this.notifyStatus();
      }
    } catch (e: any) {
      this.currentStatus.error = e.message;
      this.notifyStatus();
    }
    return this.currentStatus;
  }

  public async stopSimulation(): Promise<SignalRStatus> {
    try {
      const res = await fetch('/api/f1-live/stop-simulate', { method: 'POST' });
      const data = await res.json();
      if (data.status) {
        this.currentStatus = { ...this.currentStatus, ...data.status };
        this.notifyStatus();
      }
    } catch {
      // ignore
    }
    return this.currentStatus;
  }

  // Subscriber callbacks
  public subscribeStatus(cb: StatusCallback): () => void {
    this.statusListeners.add(cb);
    cb(this.currentStatus);
    return () => this.statusListeners.delete(cb);
  }

  public subscribePackets(cb: PacketCallback): () => void {
    this.packetListeners.add(cb);
    return () => this.packetListeners.delete(cb);
  }

  public subscribeTelemetry(cb: TelemetryCallback): () => void {
    this.telemetryListeners.add(cb);
    cb(this.telemetryState);
    return () => this.telemetryListeners.delete(cb);
  }

  private notifyStatus() {
    this.statusListeners.forEach((cb) => cb(this.currentStatus));
  }

  private notifyPacket(pkt: LiveRawPacket) {
    this.packetListeners.forEach((cb) => cb(pkt));
  }

  private notifyTelemetry() {
    this.telemetryListeners.forEach((cb) => cb(this.telemetryState));
  }
}

export const f1SignalRClient = new F1SignalRClientService();
