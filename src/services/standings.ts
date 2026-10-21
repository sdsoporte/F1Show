import {
  ChampionshipDriverRecord,
  ChampionshipTeamRecord,
  Driver,
  ProvisionalDriverStanding,
  ProvisionalTeamStanding,
} from '../types/f1';

export const RACE_POINTS_SCALE = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1];

export function getPointsForPosition(position: number): number {
  if (position >= 1 && position <= 10) {
    return RACE_POINTS_SCALE[position - 1];
  }
  return 0;
}

/**
 * Computes provisional World Drivers' Championship standings based on
 * pre-race baseline and current running order.
 */
export function computeProvisionalDriverStandings(
  runningOrder: Array<{ driverNumber: number; position: number }>,
  championshipDrivers: ChampionshipDriverRecord[],
  driversMap: Map<number, Driver>,
  fastestLapHolderNumber: number | null = null,
  year: number = 2024
): ProvisionalDriverStanding[] {
  const champMap = new Map<number, ChampionshipDriverRecord>();
  championshipDrivers.forEach(r => champMap.set(r.driver_number, r));

  const driverRacePos = new Map<number, number>();
  runningOrder.forEach(r => driverRacePos.set(r.driverNumber, r.position));

  // Determine if fastest lap gets a point (must be in top 10 for 2024 rules)
  let bonusDriver: number | null = null;
  if (year === 2024 && fastestLapHolderNumber !== null) {
    const pos = driverRacePos.get(fastestLapHolderNumber);
    if (pos && pos <= 10) {
      bonusDriver = fastestLapHolderNumber;
    }
  }

  // Calculate points for all championship drivers
  const results: ProvisionalDriverStanding[] = [];

  // Include all drivers from championship table, plus any in running order
  const allDriverNumbers = new Set<number>([
    ...champMap.keys(),
    ...runningOrder.map(r => r.driverNumber),
  ]);

  allDriverNumbers.forEach(driverNum => {
    const champ = champMap.get(driverNum);
    const startPoints = champ ? champ.points_start : 0;
    const startPosition = champ ? champ.position_start : 99;

    const currentPos = driverRacePos.get(driverNum) ?? 99;
    let earned = getPointsForPosition(currentPos);
    if (bonusDriver === driverNum) {
      earned += 1;
    }

    results.push({
      driverNumber: driverNum,
      driver: driversMap.get(driverNum) || null,
      startPoints,
      startPosition,
      currentRacePosition: currentPos,
      racePointsEarned: earned,
      provisionalTotalPoints: startPoints + earned,
      provisionalRank: 0,
      tiedWithCount: 0,
    });
  });

  // Sort by total points descending, tie-breaker by driver_number ascending
  results.sort((a, b) => {
    if (b.provisionalTotalPoints !== a.provisionalTotalPoints) {
      return b.provisionalTotalPoints - a.provisionalTotalPoints;
    }
    return a.driverNumber - b.driverNumber;
  });

  // Assign ranks and count ties
  const pointsCounts = new Map<number, number>();
  results.forEach(r => {
    pointsCounts.set(r.provisionalTotalPoints, (pointsCounts.get(r.provisionalTotalPoints) || 0) + 1);
  });

  for (let i = 0; i < results.length; i++) {
    results[i].provisionalRank = i + 1;
    results[i].tiedWithCount = (pointsCounts.get(results[i].provisionalTotalPoints) || 1) - 1;
  }

  return results;
}

/**
 * Computes provisional World Constructors' Championship standings.
 */
export function computeProvisionalTeamStandings(
  driverStandings: ProvisionalDriverStanding[],
  championshipTeams: ChampionshipTeamRecord[]
): ProvisionalTeamStanding[] {
  const teamStartMap = new Map<string, ChampionshipTeamRecord>();
  championshipTeams.forEach(t => teamStartMap.set(t.team_name, t));

  // Sum race points per team
  const teamEarnedMap = new Map<string, { points: number; colour: string }>();

  for (const ds of driverStandings) {
    if (ds.driver) {
      const team = ds.driver.team_name;
      const current = teamEarnedMap.get(team) || { points: 0, colour: ds.driver.team_colour };
      current.points += ds.racePointsEarned;
      teamEarnedMap.set(team, current);
    }
  }

  const results: ProvisionalTeamStanding[] = [];
  const allTeamNames = new Set<string>([...teamStartMap.keys(), ...teamEarnedMap.keys()]);

  allTeamNames.forEach(teamName => {
    const startRecord = teamStartMap.get(teamName);
    const startPoints = startRecord ? startRecord.points_start : 0;
    const startPosition = startRecord ? startRecord.position_start : 99;
    const earnedData = teamEarnedMap.get(teamName) || { points: 0, colour: '71717a' };

    results.push({
      teamName,
      teamColour: earnedData.colour,
      startPoints,
      startPosition,
      racePointsEarned: earnedData.points,
      provisionalTotalPoints: startPoints + earnedData.points,
      provisionalRank: 0,
      tiedWithCount: 0,
    });
  });

  // Sort by points descending, startPosition ascending, teamName
  results.sort((a, b) => {
    if (b.provisionalTotalPoints !== a.provisionalTotalPoints) {
      return b.provisionalTotalPoints - a.provisionalTotalPoints;
    }
    if (a.startPosition !== b.startPosition) {
      return a.startPosition - b.startPosition;
    }
    return a.teamName.localeCompare(b.teamName);
  });

  const pointsCounts = new Map<number, number>();
  results.forEach(r => {
    pointsCounts.set(r.provisionalTotalPoints, (pointsCounts.get(r.provisionalTotalPoints) || 0) + 1);
  });

  for (let i = 0; i < results.length; i++) {
    results[i].provisionalRank = i + 1;
    results[i].tiedWithCount = (pointsCounts.get(results[i].provisionalTotalPoints) || 1) - 1;
  }

  return results;
}
