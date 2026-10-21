import { DetectedEvent, SalienceWindow } from '../types/f1';

/**
 * Derives the window's salience projection from the event prefix.
 * The window begins at the first LAP_COMPLETED event and runs to the current event.
 */
export function computeSalience(eventsPrefix: DetectedEvent[]): SalienceWindow {
  const emptyResult: SalienceWindow = {
    fastestLap: null,
    fastOutliers: [],
    slowOutliers: [],
    medianDuration: null,
    biggestGainers: [],
    biggestLosers: [],
    busiestDriver: null,
    pitStops: [],
    activeFlags: [],
  };

  if (!eventsPrefix || eventsPrefix.length === 0) {
    return emptyResult;
  }

  // Find index of first lap_completed event
  const firstLapIndex = eventsPrefix.findIndex(e => e.eventType === 'lap_completed');
  if (firstLapIndex === -1) {
    return emptyResult;
  }

  // The active window is from first lap completed to the current event
  const windowEvents = eventsPrefix.slice(firstLapIndex);

  // 1. Position tracking inside the window
  const firstPositions = new Map<number, { pos: number; orderIndex: number }>();
  const latestPositions = new Map<number, number>();
  const positionChangeCounts = new Map<number, number>();

  for (let i = 0; i < windowEvents.length; i++) {
    const e = windowEvents[i];
    if (e.eventType === 'position_change' && e.driverNumber !== null && typeof e.evidence.position === 'number') {
      const driver = e.driverNumber;
      const pos = e.evidence.position;

      if (!firstPositions.has(driver)) {
        firstPositions.set(driver, { pos, orderIndex: i });
      }
      latestPositions.set(driver, pos);
      positionChangeCounts.set(driver, (positionChangeCounts.get(driver) || 0) + 1);
    }
  }

  // Calculate biggest gainers and losers
  const deltas: Array<{ driverNumber: number; delta: number; startPos: number; currentPos: number }> = [];

  firstPositions.forEach((first, driver) => {
    const current = latestPositions.get(driver);
    if (current !== undefined) {
      // delta = firstPos - currentPos (positive means gained places, e.g. P10 -> P4 is +6)
      const delta = first.pos - current;
      if (delta !== 0) {
        deltas.push({
          driverNumber: driver,
          delta,
          startPos: first.pos,
          currentPos: current,
        });
      }
    }
  });

  let biggestGainers: SalienceWindow['biggestGainers'] = [];
  let biggestLosers: SalienceWindow['biggestLosers'] = [];

  const gains = deltas.filter(d => d.delta > 0);
  if (gains.length > 0) {
    const maxGain = Math.max(...gains.map(g => g.delta));
    biggestGainers = gains.filter(g => g.delta === maxGain);
  }

  const losses = deltas.filter(d => d.delta < 0);
  if (losses.length > 0) {
    const maxLoss = Math.min(...losses.map(l => l.delta));
    biggestLosers = losses.filter(l => l.delta === maxLoss);
  }

  // Busiest driver
  let busiestDriver: SalienceWindow['busiestDriver'] = null;
  let maxChanges = 0;
  let bestOrderIndex = Infinity;
  let bestDriverNum = Infinity;

  positionChangeCounts.forEach((count, driver) => {
    const firstObs = firstPositions.get(driver)?.orderIndex ?? Infinity;
    if (
      count > maxChanges ||
      (count === maxChanges && firstObs < bestOrderIndex) ||
      (count === maxChanges && firstObs === bestOrderIndex && driver < bestDriverNum)
    ) {
      maxChanges = count;
      bestOrderIndex = firstObs;
      bestDriverNum = driver;
      busiestDriver = { driverNumber: driver, changeCount: count };
    }
  });

  // 2. Lap durations, fastest lap and outliers (lap_number >= 2)
  const validLaps: Array<{ driverNumber: number; lapNumber: number; duration: number }> = [];

  for (const e of windowEvents) {
    if (e.eventType === 'lap_completed' && e.driverNumber !== null) {
      const lapNum = e.evidence.lap_number;
      const duration = e.evidence.lap_duration;
      if (typeof lapNum === 'number' && lapNum >= 2 && typeof duration === 'number' && duration > 0) {
        validLaps.push({
          driverNumber: e.driverNumber,
          lapNumber: lapNum,
          duration,
        });
      }
    }
  }

  let fastestLap: SalienceWindow['fastestLap'] = null;
  let medianDuration: number | null = null;
  let fastOutliers: SalienceWindow['fastOutliers'] = [];
  let slowOutliers: SalienceWindow['slowOutliers'] = [];

  if (validLaps.length > 0) {
    // Find min duration
    validLaps.sort((a, b) => a.duration - b.duration);
    fastestLap = validLaps[0];

    // Compute median
    const durations = validLaps.map(l => l.duration).sort((a, b) => a - b);
    const mid = Math.floor(durations.length / 2);
    medianDuration =
      durations.length % 2 === 0
        ? (durations[mid - 1] + durations[mid]) / 2
        : durations[mid];

    // Outlier fences
    const fastFence = 0.75 * medianDuration;
    const slowFence = 1.25 * medianDuration;

    fastOutliers = validLaps.filter(l => l.duration < fastFence);
    slowOutliers = validLaps.filter(l => l.duration > slowFence);
  }

  // 3. Pit stops in the window
  const pitStops: SalienceWindow['pitStops'] = [];
  for (const e of windowEvents) {
    if (e.eventType === 'pit_stop' && e.driverNumber !== null) {
      pitStops.push({
        driverNumber: e.driverNumber,
        lapNumber: e.evidence.lap_number || 0,
        stopDuration: typeof e.evidence.stop_duration === 'number' ? e.evidence.stop_duration : null,
      });
    }
  }

  // 4. Flags and race control
  const activeFlags: SalienceWindow['activeFlags'] = [];
  for (const e of windowEvents) {
    if (e.eventType === 'race_control' && e.evidence.flag) {
      activeFlags.push({
        flag: String(e.evidence.flag),
        sector: typeof e.evidence.sector === 'number' ? e.evidence.sector : null,
        message: String(e.evidence.message || ''),
      });
    }
  }

  return {
    fastestLap,
    fastOutliers,
    slowOutliers,
    medianDuration,
    biggestGainers,
    biggestLosers,
    busiestDriver,
    pitStops,
    activeFlags,
  };
}
