/**
 * Advanced NBA Analytics and Machine Learning Models
 * Implements RAPTOR-style, EPM-style, and other advanced metrics
 */

// Player Impact Metrics Interface
export interface PlayerImpactMetrics {
  // Basic Stats
  playerId: string;
  playerName: string;
  team: string;
  position: string;
  minutesPlayed: number;
  gamesPlayed: number;

  // Advanced Impact Metrics (RAPTOR-style)
  offensiveRAPTOR: number;
  defensiveRAPTOR: number;
  totalRAPTOR: number;
  
  // EPM-style Metrics
  offensiveEPM: number;
  defensiveEPM: number;
  totalEPM: number;
  
  // LEBRON-style Metrics
  offensiveLEBRON: number;
  defensiveLEBRON: number;
  totalLEBRON: number;
  
  // Traditional Advanced Stats
  per: number;
  trueShooting: number;
  usageRate: number;
  winShares: number;
  winSharesPer48: number;
  bpm: number;
  vorp: number;
  
  // Tracking-based Metrics
  defenseImpact: number;
  playmaking: number;
  rebounding: number;
  shooting: number;
  
  // Contextual Metrics
  clutchPerformance: number;
  playoffImpact: number;
  versatility: number;
  durability: number;
  
  // Predictive Metrics
  projectedWins: number;
  marketValue: number;
  injuryRisk: number;
  
  // Percentile Rankings
  overallPercentile: number;
  offensePercentile: number;
  defensePercentile: number;
}

// Team Impact Metrics Interface
export interface TeamImpactMetrics {
  teamId: string;
  teamName: string;
  season: string;
  
  // Four Factors
  effectiveFieldGoalPct: number;
  turnoverRate: number;
  offensiveReboundPct: number;
  freeThrowRate: number;
  
  // Opponent Four Factors
  oppEffectiveFieldGoalPct: number;
  oppTurnoverRate: number;
  oppOffensiveReboundPct: number;
  oppFreeThrowRate: number;
  
  // Advanced Team Metrics
  offensiveRating: number;
  defensiveRating: number;
  netRating: number;
  pace: number;
  
  // Strength of Schedule
  strengthOfSchedule: number;
  strengthOfScheduleRank: number;
  
  // Clutch Performance
  clutchRecord: string;
  clutchNetRating: number;
  
  // Playoff Projections
  playoffProbability: number;
  projectedWins: number;
  championshipOdds: number;
  
  // Team Chemistry Metrics
  assistRatio: number;
  ballMovement: number;
  defensiveRotations: number;
  
  // Injury Impact
  injuryImpact: number;
  depthScore: number;
}

/**
 * RAPTOR-style Player Impact Model
 * Based on FiveThirtyEight's RAPTOR methodology
 */
export class RAPTORModel {
  /**
   * Calculate RAPTOR ratings for a player
   */
  static calculateRAPTOR(playerStats: any): { offensive: number; defensive: number; total: number } {
    // Offensive RAPTOR components
    const shootingImpact = this.calculateShootingImpact(playerStats);
    const playmakingImpact = this.calculatePlaymakingImpact(playerStats);
    const reboundingImpact = this.calculateReboundingImpact(playerStats);
    
    // Defensive RAPTOR components
    const defenseImpact = this.calculateDefenseImpact(playerStats);
    const stealImpact = this.calculateStealImpact(playerStats);
    const blockImpact = this.calculateBlockImpact(playerStats);
    
    // Position adjustments
    const positionAdjustment = this.getPositionAdjustment(playerStats.position);
    
    // Minutes-based weighting
    const minutesWeight = Math.min(1.0, playerStats.minutesPlayed / 2000);
    
    const offensiveRAPTOR = (shootingImpact + playmakingImpact + reboundingImpact) * minutesWeight + positionAdjustment.offensive;
    const defensiveRAPTOR = (defenseImpact + stealImpact + blockImpact) * minutesWeight + positionAdjustment.defensive;
    
    return {
      offensive: Math.round(offensiveRAPTOR * 100) / 100,
      defensive: Math.round(defensiveRAPTOR * 100) / 100,
      total: Math.round((offensiveRAPTOR + defensiveRAPTOR) * 100) / 100
    };
  }
  
  private static calculateShootingImpact(stats: any): number {
    const tsPct = stats.trueShooting || 0.55;
    const leagueAvgTS = 0.566;
    const fgAttempts = stats.fieldGoalAttempts || 0;
    
    return (tsPct - leagueAvgTS) * fgAttempts * 0.02;
  }
  
  private static calculatePlaymakingImpact(stats: any): number {
    const assistRatio = stats.assistRatio || 0.15;
    const turnoverRatio = stats.turnoverRatio || 0.12;
    const usageRate = stats.usageRate || 0.20;
    
    return (assistRatio * 2 - turnoverRatio) * usageRate * 10;
  }
  
  private static calculateReboundingImpact(stats: any): number {
    const reboundRate = (stats.totalRebounds || 0) / (stats.minutesPlayed || 1) * 48;
    const expectedRebounds = this.getExpectedRebounds(stats.position);
    
    return (reboundRate - expectedRebounds) * 0.1;
  }
  
  private static calculateDefenseImpact(stats: any): number {
    const defensiveRating = stats.defensiveRating || 110;
    const leagueAvgDefRating = 112;
    const minutesPlayed = stats.minutesPlayed || 0;
    
    return (leagueAvgDefRating - defensiveRating) / 100 * (minutesPlayed / 2000);
  }
  
  private static calculateStealImpact(stats: any): number {
    const stealPct = stats.stealPercentage || 0.015;
    const leagueAvgStealPct = 0.018;
    
    return (stealPct - leagueAvgStealPct) * 100;
  }
  
  private static calculateBlockImpact(stats: any): number {
    const blockPct = stats.blockPercentage || 0.02;
    const leagueAvgBlockPct = 0.025;
    
    return (blockPct - leagueAvgBlockPct) * 50;
  }
  
  private static getPositionAdjustment(position: string): { offensive: number; defensive: number } {
    const adjustments: Record<string, { offensive: number; defensive: number }> = {
      'PG': { offensive: 0.5, defensive: -0.3 },
      'SG': { offensive: 0.2, defensive: -0.1 },
      'SF': { offensive: 0.0, defensive: 0.0 },
      'PF': { offensive: -0.2, defensive: 0.2 },
      'C': { offensive: -0.5, defensive: 0.5 }
    };
    
    return adjustments[position] || { offensive: 0, defensive: 0 };
  }
  
  private static getExpectedRebounds(position: string): number {
    const expectedRebounds: Record<string, number> = {
      'PG': 4.5,
      'SG': 5.0,
      'SF': 6.5,
      'PF': 8.5,
      'C': 10.5
    };
    
    return expectedRebounds[position] || 6.0;
  }
}

/**
 * EPM-style Player Impact Model
 * Based on Dunks and Threes EPM methodology
 */
export class EPMModel {
  /**
   * Calculate EPM ratings for a player
   */
  static calculateEPM(playerStats: any, teamStats: any): { offensive: number; defensive: number; total: number } {
    // Box score components
    const boxScoreOffense = this.calculateBoxScoreOffense(playerStats);
    const boxScoreDefense = this.calculateBoxScoreDefense(playerStats);
    
    // Tracking data components
    const trackingOffense = this.calculateTrackingOffense(playerStats);
    const trackingDefense = this.calculateTrackingDefense(playerStats);
    
    // Team context adjustments
    const teamAdjustment = this.calculateTeamAdjustment(playerStats, teamStats);
    
    const offensiveEPM = boxScoreOffense + trackingOffense + teamAdjustment.offensive;
    const defensiveEPM = boxScoreDefense + trackingDefense + teamAdjustment.defensive;
    
    return {
      offensive: Math.round(offensiveEPM * 100) / 100,
      defensive: Math.round(defensiveEPM * 100) / 100,
      total: Math.round((offensiveEPM + defensiveEPM) * 100) / 100
    };
  }
  
  private static calculateBoxScoreOffense(stats: any): number {
    const scoring = (stats.points || 0) * 0.04;
    const assists = (stats.assists || 0) * 0.15;
    const turnovers = (stats.turnovers || 0) * -0.2;
    const shooting = (stats.trueShooting || 0.55 - 0.566) * 5;
    
    return scoring + assists + turnovers + shooting;
  }
  
  private static calculateBoxScoreDefense(stats: any): number {
    const steals = (stats.steals || 0) * 0.3;
    const blocks = (stats.blocks || 0) * 0.25;
    const rebounds = (stats.defensiveRebounds || 0) * 0.05;
    const fouls = (stats.personalFouls || 0) * -0.1;
    
    return steals + blocks + rebounds + fouls;
  }
  
  private static calculateTrackingOffense(stats: any): number {
    // Simulated tracking data impact
    const spacing = (stats.threePtAttempts || 0) / (stats.fieldGoalAttempts || 1) * 2;
    const ballHandling = (stats.timeOfPossession || 5) / 10;
    const offBallMovement = Math.random() * 0.5; // Would use real tracking data
    
    return spacing + ballHandling + offBallMovement;
  }
  
  private static calculateTrackingDefense(stats: any): number {
    // Simulated tracking data impact
    const contestedShots = Math.random() * 1.5; // Would use real tracking data
    const deflections = (stats.deflections || 2) * 0.1;
    const defensiveRotations = Math.random() * 1.0; // Would use real tracking data
    
    return contestedShots + deflections + defensiveRotations;
  }
  
  private static calculateTeamAdjustment(playerStats: any, teamStats: any): { offensive: number; defensive: number } {
    const teamOffRating = teamStats.offensiveRating || 110;
    const teamDefRating = teamStats.defensiveRating || 110;
    const leagueAvgOffRating = 112;
    const leagueAvgDefRating = 112;
    
    const offensiveAdjustment = (teamOffRating - leagueAvgOffRating) / 100;
    const defensiveAdjustment = (leagueAvgDefRating - teamDefRating) / 100;
    
    return {
      offensive: offensiveAdjustment,
      defensive: defensiveAdjustment
    };
  }
}

/**
 * Team Chemistry and Network Analysis
 */
export class TeamChemistryModel {
  /**
   * Calculate team chemistry metrics
   */
  static calculateTeamChemistry(teamStats: any, playerStats: any[]): any {
    const ballMovement = this.calculateBallMovement(teamStats);
    const defensiveRotations = this.calculateDefensiveRotations(teamStats);
    const lineupSynergy = this.calculateLineupSynergy(playerStats);
    const leadershipImpact = this.calculateLeadershipImpact(playerStats);
    
    return {
      ballMovement,
      defensiveRotations,
      lineupSynergy,
      leadershipImpact,
      overallChemistry: (ballMovement + defensiveRotations + lineupSynergy + leadershipImpact) / 4
    };
  }
  
  private static calculateBallMovement(teamStats: any): number {
    const assistRatio = teamStats.assistRatio || 0.6;
    const passesPerGame = teamStats.passesPerGame || 300;
    const secondaryAssists = teamStats.secondaryAssists || 10;
    
    return (assistRatio * 50 + passesPerGame / 10 + secondaryAssists) / 3;
  }
  
  private static calculateDefensiveRotations(teamStats: any): number {
    const deflections = teamStats.deflections || 15;
    const contestedShots = teamStats.contestedShots || 50;
    const helpDefense = teamStats.helpDefense || 20;
    
    return (deflections * 2 + contestedShots + helpDefense) / 3;
  }
  
  private static calculateLineupSynergy(playerStats: any[]): number {
    // Calculate how well players complement each other
    let synergyScore = 0;
    const numPlayers = playerStats.length;
    
    for (let i = 0; i < numPlayers; i++) {
      for (let j = i + 1; j < numPlayers; j++) {
        synergyScore += this.calculatePlayerSynergy(playerStats[i], playerStats[j]);
      }
    }
    
    return synergyScore / (numPlayers * (numPlayers - 1) / 2);
  }
  
  private static calculatePlayerSynergy(player1: any, player2: any): number {
    // Simplified synergy calculation
    const skillComplementarity = this.calculateSkillComplementarity(player1, player2);
    const positionFit = this.calculatePositionFit(player1.position, player2.position);
    const playStyleFit = this.calculatePlayStyleFit(player1, player2);
    
    return (skillComplementarity + positionFit + playStyleFit) / 3;
  }
  
  private static calculateSkillComplementarity(player1: any, player2: any): number {
    // Players with different strengths complement each other better
    const shootingDiff = Math.abs((player1.threePtPct || 0.35) - (player2.threePtPct || 0.35));
    const playmakingDiff = Math.abs((player1.assistRatio || 0.15) - (player2.assistRatio || 0.15));
    const defenseDiff = Math.abs((player1.defensiveRating || 110) - (player2.defensiveRating || 110));
    
    return (shootingDiff * 100 + playmakingDiff * 100 + defenseDiff / 10) / 3;
  }
  
  private static calculatePositionFit(pos1: string, pos2: string): number {
    // Position compatibility matrix
    const compatibility: Record<string, Record<string, number>> = {
      'PG': { 'PG': 0.3, 'SG': 0.8, 'SF': 0.7, 'PF': 0.6, 'C': 0.5 },
      'SG': { 'PG': 0.8, 'SG': 0.4, 'SF': 0.9, 'PF': 0.7, 'C': 0.6 },
      'SF': { 'PG': 0.7, 'SG': 0.9, 'SF': 0.5, 'PF': 0.8, 'C': 0.7 },
      'PF': { 'PG': 0.6, 'SG': 0.7, 'SF': 0.8, 'PF': 0.4, 'C': 0.9 },
      'C': { 'PG': 0.5, 'SG': 0.6, 'SF': 0.7, 'PF': 0.9, 'C': 0.3 }
    };
    
    return compatibility[pos1]?.[pos2] || 0.5;
  }
  
  private static calculatePlayStyleFit(player1: any, player2: any): number {
    // Simplified play style compatibility
    const pace1 = player1.pace || 100;
    const pace2 = player2.pace || 100;
    const paceDiff = Math.abs(pace1 - pace2);
    
    const usage1 = player1.usageRate || 0.2;
    const usage2 = player2.usageRate || 0.2;
    const usageFit = 1 - Math.abs(usage1 + usage2 - 0.4); // Optimal combined usage around 40%
    
    return Math.max(0, 1 - paceDiff / 20) * usageFit;
  }
  
  private static calculateLeadershipImpact(playerStats: any[]): number {
    // Identify leaders and calculate their impact
    const leaders = playerStats.filter(p => (p.experience || 0) > 5 && (p.minutesPlayed || 0) > 1500);
    const leadershipScore = leaders.reduce((sum, leader) => {
      const experience = leader.experience || 0;
      const performance = leader.per || 15;
      const clutch = leader.clutchPerformance || 0;
      
      return sum + (experience * 0.1 + performance * 0.5 + clutch * 2);
    }, 0);
    
    return Math.min(100, leadershipScore / leaders.length || 0);
  }
}
