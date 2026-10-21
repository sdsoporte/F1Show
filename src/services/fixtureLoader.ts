import {
  ChampionshipDriverRecord,
  ChampionshipTeamRecord,
  Driver,
  SessionRecord,
} from '../types/f1';
import { RawSessionPayloads } from './collector';

// Import session 9655 fixtures (Lusail 2024 Race)
import s9655Sessions from '../../fixtures/openf1/9655/sessions.json';
import s9655Drivers from '../../fixtures/openf1/9655/drivers.json';
import s9655Position from '../../fixtures/openf1/9655/position.json';
import s9655Laps from '../../fixtures/openf1/9655/laps.json';
import s9655Pit from '../../fixtures/openf1/9655/pit.json';
import s9655Stints from '../../fixtures/openf1/9655/stints.json';
import s9655RaceControl from '../../fixtures/openf1/9655/race_control.json';
import s9655ChampDrivers from '../../fixtures/openf1/9655/championship_drivers.json';
import s9655ChampTeams from '../../fixtures/openf1/9655/championship_teams.json';
import s9655Result from '../../fixtures/openf1/9655/session_result.json';

// Import session 9608 fixtures (Austin 2024 Qualifying)
import s9608Sessions from '../../fixtures/openf1/9608/sessions.json';
import s9608Drivers from '../../fixtures/openf1/9608/drivers.json';
import s9608Position from '../../fixtures/openf1/9608/position.json';
import s9608Laps from '../../fixtures/openf1/9608/laps.json';
import s9608Pit from '../../fixtures/openf1/9608/pit.json';
import s9608Stints from '../../fixtures/openf1/9608/stints.json';
import s9608RaceControl from '../../fixtures/openf1/9608/race_control.json';
import s9608Result from '../../fixtures/openf1/9608/session_result.json';

// Fallback top-level championship fixtures for 9608 if needed
import topChampDrivers from '../../fixtures/openf1/championship_drivers.json';
import topChampTeams from '../../fixtures/openf1/championship_teams.json';
import topIntervals from '../../fixtures/openf1/intervals.json';

export interface LoadedSessionData {
  session: SessionRecord;
  drivers: Driver[];
  driversMap: Map<number, Driver>;
  payloads: RawSessionPayloads;
  championshipDrivers: ChampionshipDriverRecord[];
  championshipTeams: ChampionshipTeamRecord[];
}

export const PRESET_SESSIONS = [
  {
    key: 9655,
    name: '2024 Qatar Grand Prix (Lusail - Race)',
    type: 'Race',
    year: 2024,
    circuit: 'Lusail International Circuit',
    country: 'Qatar',
    date: '2024-12-01',
    description: 'Round 23: World Championship showdown, safety cars, high tyre wear and intense tactical battles.',
  },
  {
    key: 9608,
    name: '2024 United States Grand Prix (Austin - Qualifying)',
    type: 'Qualifying',
    year: 2024,
    circuit: 'Circuit of the Americas',
    country: 'United States',
    date: '2024-10-19',
    description: 'Qualifying cutoffs, track limits, and pole position shootout at COTA.',
  },
  {
    key: 9999,
    name: '🔴 Official F1 Live Timing (SignalR Live Stream)',
    type: 'Live Stream',
    year: 2026,
    circuit: 'Circuit of the Americas / Live Circuit',
    country: 'United States',
    date: '2026-10-21',
    description: 'Live real-time feed connected directly to official F1 Live Timing SignalR stream.',
  },
];

export function getSessionData(sessionKey: number): LoadedSessionData {
  if (sessionKey === 9999) {
    // Dynamic F1 Live SignalR session
    const driversList = s9655Drivers as Driver[];
    const driversMap = new Map<number, Driver>();
    driversList.forEach(d => driversMap.set(d.driver_number, d));

    const liveSessionRec: SessionRecord = {
      session_key: 9999,
      session_name: 'F1 Live Timing Stream (SignalR)',
      session_type: 'Live Race',
      date_start: new Date().toISOString(),
      date_end: new Date(Date.now() + 7200000).toISOString(),
      circuit_short_name: 'Austin',
      country_code: 'USA',
      country_name: 'United States',
      location: 'Circuit of the Americas',
      year: 2026,
    };

    return {
      session: liveSessionRec,
      drivers: driversList,
      driversMap,
      payloads: {
        position: s9655Position as any[],
        laps: s9655Laps as any[],
        pit: s9655Pit as any[],
        stints: s9655Stints as any[],
        race_control: s9655RaceControl as any[],
        drivers: driversList,
        session_result: s9655Result as any[],
        sessions: [liveSessionRec],
        championship_drivers: s9655ChampDrivers as any[],
        championship_teams: s9655ChampTeams as any[],
      },
      championshipDrivers: s9655ChampDrivers as ChampionshipDriverRecord[],
      championshipTeams: s9655ChampTeams as ChampionshipTeamRecord[],
    };
  }
  if (sessionKey === 9608) {
    const sessionRec = (s9608Sessions as any[])[0] as SessionRecord;
    const driversList = s9608Drivers as Driver[];
    const driversMap = new Map<number, Driver>();
    driversList.forEach(d => driversMap.set(d.driver_number, d));

    const payloads: RawSessionPayloads = {
      position: s9608Position as any[],
      laps: s9608Laps as any[],
      pit: s9608Pit as any[],
      stints: s9608Stints as any[],
      race_control: s9608RaceControl as any[],
      drivers: driversList,
      session_result: s9608Result as any[],
      sessions: s9608Sessions as any[],
      intervals: topIntervals as any[],
    };

    return {
      session: sessionRec,
      drivers: driversList,
      driversMap,
      payloads,
      championshipDrivers: topChampDrivers as ChampionshipDriverRecord[],
      championshipTeams: topChampTeams as ChampionshipTeamRecord[],
    };
  }

  // Default to session 9655
  const sessionRec = (s9655Sessions as any[])[0] as SessionRecord;
  const driversList = s9655Drivers as Driver[];
  const driversMap = new Map<number, Driver>();
  driversList.forEach(d => driversMap.set(d.driver_number, d));

  const payloads: RawSessionPayloads = {
    position: s9655Position as any[],
    laps: s9655Laps as any[],
    pit: s9655Pit as any[],
    stints: s9655Stints as any[],
    race_control: s9655RaceControl as any[],
    drivers: driversList,
    session_result: s9655Result as any[],
    sessions: s9655Sessions as any[],
    championship_drivers: s9655ChampDrivers as any[],
    championship_teams: s9655ChampTeams as any[],
  };

  return {
    session: sessionRec,
    drivers: driversList,
    driversMap,
    payloads,
    championshipDrivers: s9655ChampDrivers as ChampionshipDriverRecord[],
    championshipTeams: s9655ChampTeams as ChampionshipTeamRecord[],
  };
}
