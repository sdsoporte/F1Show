export type EventType =
  | 'session_start'
  | 'session_end'
  | 'position_change'
  | 'lap_completed'
  | 'personal_best_lap'
  | 'fastest_lap'
  | 'sector_best'
  | 'flag'
  | 'safety_car'
  | 'virtual_safety_car'
  | 'pit_stop'
  | 'stint_start'
  | 'interval_update'
  | 'overtake'
  | 'race_control';

export interface Provenance {
  endpoint: string;
  sourceUrl?: string;
  observedAt: string;
}

export interface DetectedEvent {
  eventId: string;
  eventType: EventType;
  sessionKey: number;
  driverNumber: number | null;
  eventTime: string | null;
  family: 'position' | 'laps' | 'pit' | 'stints' | 'race_control';
  recordIndex: number;
  evidence: Record<string, any>;
  references: string[];
  rawRecord: any;
}

export interface Driver {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  broadcast_name: string;
  full_name: string;
  name_acronym: string;
  team_name: string;
  team_colour: string;
  first_name: string;
  last_name: string;
  headshot_url: string | null;
  country_code: string;
}

export interface Lap {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  lap_number: number;
  lap_duration: number | null;
  date_start: string | null;
  duration_sector_1?: number | null;
  duration_sector_2?: number | null;
  duration_sector_3?: number | null;
  segments_sector_1?: number[];
  segments_sector_2?: number[];
  segments_sector_3?: number[];
  is_pit_out_lap?: boolean;
  i1_speed?: number | null;
  i2_speed?: number | null;
  st_speed?: number | null;
}

export interface PositionRecord {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  position: number;
  date: string | null;
}

export interface PitRecord {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  lap_number: number;
  lane_duration: number | null;
  pit_duration: number | null;
  stop_duration: number | null;
  date: string | null;
}

export interface StintRecord {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  stint_number: number;
  lap_start: number;
  lap_end: number | null;
  compound: 'SOFT' | 'MEDIUM' | 'HARD' | 'INTERMEDIATE' | 'WET' | string;
  tyre_age_at_start: number;
}

export interface RaceControlRecord {
  meeting_key?: number;
  session_key?: number;
  category: string;
  flag?: string | null;
  scope?: string | null;
  sector?: number | null;
  lap_number?: number | null;
  qualifying_phase?: string | null;
  message: string;
  date: string | null;
}

export interface IntervalRecord {
  meeting_key?: number;
  session_key?: number;
  driver_number: number;
  gap_to_leader: number | string | null;
  interval: number | string | null;
  date: string | null;
}

export interface SessionRecord {
  session_key: number;
  session_name: string;
  session_type: string;
  date_start: string;
  date_end: string;
  meeting_key?: number;
  circuit_key?: number;
  circuit_short_name: string;
  country_key?: number;
  country_code: string;
  country_name: string;
  location: string;
  gmt_offset?: string;
  year: number;
  is_cancelled?: boolean;
}

export interface ChampionshipDriverRecord {
  session_key?: number;
  driver_number: number;
  points_start: number;
  points_current: number;
  position_start: number;
  position_current: number;
}

export interface ChampionshipTeamRecord {
  session_key?: number;
  team_name: string;
  points_start: number;
  points_current: number;
  position_start: number;
  position_current: number;
}

export type BoothSpeaker = 'lead' | 'color';
export type BoothMode = 'build' | 'climax';
export type BoothLanguage = 'es-AR' | 'es-419' | 'es-MX' | 'es-ES' | 'en';
export type TurnOutcome = 'AIRED' | 'DEGRADED' | 'REFUSED' | 'SUPPRESSED' | 'COVERED_BY_START';

export interface Turn {
  id: string;
  speaker: BoothSpeaker;
  text: string;
  evidence: string[];
  eventRef?: string;
  mode: BoothMode;
  createdAt: string;
  outcome: TurnOutcome;
  refusalReason?: string;
  driverNumber?: number | null;
}

export interface SalienceWindow {
  fastestLap: {
    driverNumber: number;
    lapNumber: number;
    duration: number;
  } | null;
  fastOutliers: Array<{
    driverNumber: number;
    lapNumber: number;
    duration: number;
  }>;
  slowOutliers: Array<{
    driverNumber: number;
    lapNumber: number;
    duration: number;
  }>;
  medianDuration: number | null;
  biggestGainers: Array<{
    driverNumber: number;
    delta: number;
    startPos: number;
    currentPos: number;
  }>;
  biggestLosers: Array<{
    driverNumber: number;
    delta: number;
    startPos: number;
    currentPos: number;
  }>;
  busiestDriver: {
    driverNumber: number;
    changeCount: number;
  } | null;
  pitStops: Array<{
    driverNumber: number;
    lapNumber: number;
    stopDuration: number | null;
  }>;
  activeFlags: Array<{
    flag: string;
    sector: number | null;
    message: string;
  }>;
}

export interface LiveDriverState {
  driverNumber: number;
  driver: Driver;
  position: number;
  previousPosition: number;
  gridPosition: number;
  positionDelta: number; // gridPosition - position (positive means gained places)
  lastLapNumber: number;
  lastLapTime: number | null;
  bestLapTime: number | null;
  isFastestLapHolder: boolean;
  currentStint: StintRecord | null;
  stintLaps: number;
  currentCompound: string;
  pitCount: number;
  inPitLane: boolean;
  gapToLeader: string;
  interval: string;
  status: 'RUNNING' | 'PIT' | 'RETIRED' | 'OUT';
}

export interface ProvisionalDriverStanding {
  driverNumber: number;
  driver: Driver | null;
  startPoints: number;
  startPosition: number;
  currentRacePosition: number;
  racePointsEarned: number;
  provisionalTotalPoints: number;
  provisionalRank: number;
  tiedWithCount: number;
}

export interface ProvisionalTeamStanding {
  teamName: string;
  teamColour: string;
  startPoints: number;
  startPosition: number;
  racePointsEarned: number;
  provisionalTotalPoints: number;
  provisionalRank: number;
  tiedWithCount: number;
}
