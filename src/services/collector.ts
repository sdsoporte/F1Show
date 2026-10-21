import { DetectedEvent, EventType } from '../types/f1';

export const FAMILY_ORDER = ['position', 'laps', 'pit', 'stints', 'race_control'] as const;

export const FAMILY_RANK: Record<string, number> = {
  position: 0,
  laps: 1,
  pit: 2,
  stints: 3,
  race_control: 4,
};

const EVENT_TYPE_MAP: Record<string, EventType> = {
  position: 'position_change',
  laps: 'lap_completed',
  pit: 'pit_stop',
  stints: 'stint_start',
  race_control: 'race_control',
};

const TIMESTAMP_FIELD: Record<string, string | null> = {
  position: 'date',
  laps: 'date_start',
  pit: 'date',
  stints: null,
  race_control: 'date',
};

const EVIDENCE_FIELDS: Record<string, string[]> = {
  position: ['position'],
  laps: [
    'lap_number',
    'lap_duration',
    'duration_sector_1',
    'duration_sector_2',
    'duration_sector_3',
    'segments_sector_1',
    'segments_sector_2',
    'segments_sector_3',
    'is_pit_out_lap',
    'i1_speed',
    'i2_speed',
    'st_speed',
  ],
  pit: ['lap_number', 'lane_duration', 'pit_duration', 'stop_duration'],
  stints: ['stint_number', 'lap_start', 'lap_end', 'compound', 'tyre_age_at_start'],
  race_control: ['category', 'flag', 'scope', 'sector', 'lap_number', 'qualifying_phase', 'message'],
};

export interface RawSessionPayloads {
  position?: any[];
  laps?: any[];
  pit?: any[];
  stints?: any[];
  race_control?: any[];
  drivers?: any[];
  intervals?: any[];
  session_result?: any[];
  championship_drivers?: any[];
  championship_teams?: any[];
  sessions?: any[];
}

/**
 * Deterministic event detection over recorded OpenF1 payloads.
 * Total ordering:
 * 1. Timestamp ascending (null/missing timestamps sort to the very end)
 * 2. Family rank (position -> laps -> pit -> stints -> race_control)
 * 3. Original record index
 */
export function collectSessionEvents(
  sessionKey: number,
  payloads: RawSessionPayloads
): DetectedEvent[] {
  const events: DetectedEvent[] = [];

  for (const family of FAMILY_ORDER) {
    const records = payloads[family] || [];
    const timestampKey = TIMESTAMP_FIELD[family];
    const allowedFields = EVIDENCE_FIELDS[family] || [];
    const eventType = EVENT_TYPE_MAP[family];

    for (let index = 0; index < records.length; index++) {
      const record = records[index];
      if (!record || typeof record !== 'object') continue;

      const eventTime = timestampKey && record[timestampKey] ? String(record[timestampKey]) : null;
      const driverNumber = typeof record.driver_number === 'number' ? record.driver_number : null;

      // Extract non-null evidence fields
      const evidence: Record<string, any> = {};
      const references: string[] = [];

      for (const field of allowedFields) {
        if (record[field] !== undefined && record[field] !== null) {
          evidence[field] = record[field];
          references.push(`${family}[${index}].${field}`);
        }
      }

      events.push({
        eventId: `${family}_${index}_${driverNumber ?? 'none'}`,
        eventType,
        sessionKey,
        driverNumber,
        eventTime,
        family: family as any,
        recordIndex: index,
        evidence,
        references,
        rawRecord: record,
      });
    }
  }

  // Sort events using the deterministic total order
  events.sort((a, b) => {
    // 1. Timestamp comparison
    const timeA = a.eventTime ? new Date(a.eventTime).getTime() : Infinity;
    const timeB = b.eventTime ? new Date(b.eventTime).getTime() : Infinity;

    if (timeA !== timeB) {
      return timeA - timeB;
    }

    // 2. Family rank
    const rankA = FAMILY_RANK[a.family] ?? 99;
    const rankB = FAMILY_RANK[b.family] ?? 99;
    if (rankA !== rankB) {
      return rankA - rankB;
    }

    // 3. Record index
    return a.recordIndex - b.recordIndex;
  });

  return events;
}

export function classifyGap(value: any): { kind: 'seconds' | 'laps' | 'leader' | 'unknown' | 'none'; value: number | null } {
  if (value === null || value === undefined || value === '') {
    return { kind: 'none', value: null };
  }
  if (typeof value === 'number') {
    return { kind: 'seconds', value };
  }
  const str = String(value).trim();
  if (str === 'LEADER' || str === '0.000') {
    return { kind: 'leader', value: 0 };
  }
  const lapMatch = str.match(/^\+(\d+)\s*LAP/i);
  if (lapMatch) {
    return { kind: 'laps', value: parseInt(lapMatch[1], 10) };
  }
  const secMatch = str.match(/^\+?([\d.]+)/);
  if (secMatch) {
    const parsed = parseFloat(secMatch[1]);
    if (!isNaN(parsed)) {
      return { kind: 'seconds', value: parsed };
    }
  }
  return { kind: 'unknown', value: null };
}
