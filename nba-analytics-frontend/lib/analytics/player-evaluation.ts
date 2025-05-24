/**
 * Comprehensive Player Evaluation System
 * Implements multiple evaluation methodologies including RAPTOR, EPM, LEBRON, and custom models
 */

export interface PlayerEvaluationResult {
  playerId: string;
  playerName: string;
  season: string;
  
  // Core Metrics
  overallGrade: string; // A+, A, B+, B, C+, C, D+, D, F
  overallScore: number; // 0-100
  
  // Impact Metrics
  offensiveImpact: number;
  defensiveImpact: number;
  totalImpact: number;
  
  // Skill Grades
  shooting: { grade: string; score: number; percentile: number };
  playmaking: { grade: string; score: number; percentile: number };
  rebounding: { grade: string; score: number; percentile: number };
  defense: { grade: string; score: number; percentile: number };
  athleticism: { grade: string; score: number; percentile: number };
  
  // Advanced Metrics
  raptor: { offensive: number; defensive: number; total: number };
  epm: { offensive: number; defensive: number; total: number };
  lebron: { offensive: number; defensive: number; total: number };
  
  // Traditional Advanced Stats
  per: number;
  trueShooting: number;
  usageRate: number;
  winShares: number;
  bpm: number;
  vorp: number;
  
  // Contextual Metrics
  clutchPerformance: number;
  playoffPerformance: number;
  durability: number;
  versatility: number;
  
  // Market Value
  estimatedValue: number; // In millions
  contractEfficiency: number;
  tradeValue: number;
  
  // Projections
  projectedGrowth: number;
  peakAge: number;
  careerTrajectory: 'ascending' | 'peak' | 'declining';
  
  // Comparisons
  similarPlayers: string[];
  historicalComparisons: string[];
  
  // Risk Factors
  injuryRisk: number;
  performanceVolatility: number;
  ageRisk: number;
}

/**
 * Comprehensive Player Evaluation Engine
 */
export class PlayerEvaluationEngine {
  /**
   * Evaluate a player using multiple methodologies
   */
  static evaluatePlayer(playerData: any, leagueContext: any): PlayerEvaluationResult {
    // Calculate core impact metrics
    const impactMetrics = this.calculateImpactMetrics(playerData, leagueContext);
    
    // Calculate skill grades
    const skillGrades = this.calculateSkillGrades(playerData, leagueContext);
    
    // Calculate advanced metrics
    const advancedMetrics = this.calculateAdvancedMetrics(playerData, leagueContext);
    
    // Calculate contextual metrics
    const contextualMetrics = this.calculateContextualMetrics(playerData, leagueContext);
    
    // Calculate market value
    const marketValue = this.calculateMarketValue(playerData, impactMetrics, leagueContext);
    
    // Calculate projections
    const projections = this.calculateProjections(playerData, impactMetrics);
    
    // Calculate risk factors
    const riskFactors = this.calculateRiskFactors(playerData, leagueContext);
    
    // Calculate overall grade and score
    const overallEvaluation = this.calculateOverallEvaluation(
      impactMetrics,
      skillGrades,
      advancedMetrics,
      contextualMetrics
    );
    
    return {
      playerId: playerData.playerId,
      playerName: playerData.playerName,
      season: playerData.season || '2023-24',
      
      overallGrade: overallEvaluation.grade,
      overallScore: overallEvaluation.score,
      
      offensiveImpact: impactMetrics.offensive,
      defensiveImpact: impactMetrics.defensive,
      totalImpact: impactMetrics.total,
      
      shooting: skillGrades.shooting,
      playmaking: skillGrades.playmaking,
      rebounding: skillGrades.rebounding,
      defense: skillGrades.defense,
      athleticism: skillGrades.athleticism,
      
      raptor: advancedMetrics.raptor,
      epm: advancedMetrics.epm,
      lebron: advancedMetrics.lebron,
      
      per: advancedMetrics.per,
      trueShooting: advancedMetrics.trueShooting,
      usageRate: advancedMetrics.usageRate,
      winShares: advancedMetrics.winShares,
      bpm: advancedMetrics.bpm,
      vorp: advancedMetrics.vorp,
      
      clutchPerformance: contextualMetrics.clutch,
      playoffPerformance: contextualMetrics.playoff,
      durability: contextualMetrics.durability,
      versatility: contextualMetrics.versatility,
      
      estimatedValue: marketValue.estimated,
      contractEfficiency: marketValue.efficiency,
      tradeValue: marketValue.trade,
      
      projectedGrowth: projections.growth,
      peakAge: projections.peakAge,
      careerTrajectory: projections.trajectory,
      
      similarPlayers: this.findSimilarPlayers(playerData, leagueContext),
      historicalComparisons: this.findHistoricalComparisons(playerData, leagueContext),
      
      injuryRisk: riskFactors.injury,
      performanceVolatility: riskFactors.volatility,
      ageRisk: riskFactors.age
    };
  }
  
  private static calculateImpactMetrics(playerData: any, leagueContext: any): any {
    // Simplified impact calculation - would use real advanced models
    const offensiveImpact = this.calculateOffensiveImpact(playerData);
    const defensiveImpact = this.calculateDefensiveImpact(playerData);
    
    return {
      offensive: offensiveImpact,
      defensive: defensiveImpact,
      total: offensiveImpact + defensiveImpact
    };
  }
  
  private static calculateOffensiveImpact(playerData: any): number {
    const scoring = (playerData.points || 0) * 0.04;
    const efficiency = ((playerData.trueShooting || 0.55) - 0.566) * 10;
    const playmaking = (playerData.assists || 0) * 0.15;
    const turnovers = (playerData.turnovers || 0) * -0.2;
    const usage = (playerData.usageRate || 0.2) * 5;
    
    return scoring + efficiency + playmaking + turnovers + usage;
  }
  
  private static calculateDefensiveImpact(playerData: any): number {
    const steals = (playerData.steals || 0) * 0.3;
    const blocks = (playerData.blocks || 0) * 0.25;
    const rebounds = (playerData.defensiveRebounds || 0) * 0.05;
    const defRating = ((playerData.defensiveRating || 110) - 112) * -0.1;
    
    return steals + blocks + rebounds + defRating;
  }
  
  private static calculateSkillGrades(playerData: any, leagueContext: any): any {
    return {
      shooting: this.gradeSkill(this.calculateShootingScore(playerData)),
      playmaking: this.gradeSkill(this.calculatePlaymakingScore(playerData)),
      rebounding: this.gradeSkill(this.calculateReboundingScore(playerData)),
      defense: this.gradeSkill(this.calculateDefenseScore(playerData)),
      athleticism: this.gradeSkill(this.calculateAthleticismScore(playerData))
    };
  }
  
  private static calculateShootingScore(playerData: any): number {
    const tsPct = playerData.trueShooting || 0.55;
    const threePtPct = playerData.threePtPct || 0.35;
    const ftPct = playerData.freeThrowPct || 0.75;
    const volume = playerData.fieldGoalAttempts || 10;
    
    // Normalize to 0-100 scale
    const tsScore = Math.min(100, Math.max(0, (tsPct - 0.45) * 200));
    const threePtScore = Math.min(100, Math.max(0, (threePtPct - 0.25) * 200));
    const ftScore = Math.min(100, Math.max(0, (ftPct - 0.60) * 250));
    const volumeBonus = Math.min(20, volume * 0.5);
    
    return (tsScore * 0.4 + threePtScore * 0.3 + ftScore * 0.2 + volumeBonus * 0.1);
  }
  
  private static calculatePlaymakingScore(playerData: any): number {
    const assistRatio = playerData.assistRatio || 0.15;
    const turnoverRatio = playerData.turnoverRatio || 0.12;
    const assists = playerData.assists || 0;
    const usageRate = playerData.usageRate || 0.2;
    
    const assistScore = Math.min(100, assistRatio * 300);
    const turnoverPenalty = Math.max(-50, turnoverRatio * -200);
    const volumeBonus = Math.min(30, assists * 3);
    const usageAdjustment = usageRate * 50;
    
    return Math.max(0, assistScore + turnoverPenalty + volumeBonus + usageAdjustment);
  }
  
  private static calculateReboundingScore(playerData: any): number {
    const reboundRate = (playerData.totalRebounds || 0) / (playerData.minutesPlayed || 1) * 48;
    const offRebPct = playerData.offensiveReboundPct || 0.05;
    const defRebPct = playerData.defensiveReboundPct || 0.15;
    
    const expectedRebounds = this.getExpectedRebounds(playerData.position);
    const reboundScore = Math.min(100, Math.max(0, (reboundRate - expectedRebounds + 5) * 10));
    const offRebScore = Math.min(50, offRebPct * 1000);
    const defRebScore = Math.min(50, defRebPct * 200);
    
    return reboundScore * 0.6 + offRebScore * 0.2 + defRebScore * 0.2;
  }
  
  private static calculateDefenseScore(playerData: any): number {
    const defRating = playerData.defensiveRating || 110;
    const steals = playerData.steals || 0;
    const blocks = playerData.blocks || 0;
    const fouls = playerData.personalFouls || 0;
    
    const defRatingScore = Math.min(100, Math.max(0, (115 - defRating) * 5));
    const stealScore = Math.min(30, steals * 15);
    const blockScore = Math.min(30, blocks * 20);
    const foulPenalty = Math.max(-20, (4 - fouls) * 5);
    
    return defRatingScore * 0.6 + stealScore * 0.2 + blockScore * 0.15 + foulPenalty * 0.05;
  }
  
  private static calculateAthleticismScore(playerData: any): number {
    // Simplified athleticism calculation based on available stats
    const pace = playerData.pace || 100;
    const minutes = playerData.minutesPlayed || 0;
    const age = playerData.age || 25;
    const steals = playerData.steals || 0;
    const blocks = playerData.blocks || 0;
    
    const paceScore = Math.min(40, (pace - 95) * 4);
    const durabilityScore = Math.min(30, minutes / 100);
    const ageScore = Math.min(20, (35 - age) * 2);
    const explosiveScore = Math.min(10, (steals + blocks) * 5);
    
    return paceScore + durabilityScore + ageScore + explosiveScore;
  }
  
  private static gradeSkill(score: number): { grade: string; score: number; percentile: number } {
    const percentile = Math.min(99, Math.max(1, score));
    let grade: string;
    
    if (score >= 95) grade = 'A+';
    else if (score >= 90) grade = 'A';
    else if (score >= 85) grade = 'A-';
    else if (score >= 80) grade = 'B+';
    else if (score >= 75) grade = 'B';
    else if (score >= 70) grade = 'B-';
    else if (score >= 65) grade = 'C+';
    else if (score >= 60) grade = 'C';
    else if (score >= 55) grade = 'C-';
    else if (score >= 50) grade = 'D+';
    else if (score >= 45) grade = 'D';
    else if (score >= 40) grade = 'D-';
    else grade = 'F';
    
    return { grade, score: Math.round(score), percentile: Math.round(percentile) };
  }
  
  private static calculateAdvancedMetrics(playerData: any, leagueContext: any): any {
    // Simplified calculations - would use real formulas
    return {
      raptor: {
        offensive: this.calculateOffensiveImpact(playerData),
        defensive: this.calculateDefensiveImpact(playerData),
        total: this.calculateOffensiveImpact(playerData) + this.calculateDefensiveImpact(playerData)
      },
      epm: {
        offensive: this.calculateOffensiveImpact(playerData) * 0.9,
        defensive: this.calculateDefensiveImpact(playerData) * 0.9,
        total: (this.calculateOffensiveImpact(playerData) + this.calculateDefensiveImpact(playerData)) * 0.9
      },
      lebron: {
        offensive: this.calculateOffensiveImpact(playerData) * 1.1,
        defensive: this.calculateDefensiveImpact(playerData) * 1.1,
        total: (this.calculateOffensiveImpact(playerData) + this.calculateDefensiveImpact(playerData)) * 1.1
      },
      per: this.calculatePER(playerData),
      trueShooting: playerData.trueShooting || 0.55,
      usageRate: playerData.usageRate || 0.2,
      winShares: this.calculateWinShares(playerData),
      bpm: this.calculateBPM(playerData),
      vorp: this.calculateVORP(playerData)
    };
  }
  
  private static calculatePER(playerData: any): number {
    // Simplified PER calculation
    const points = playerData.points || 0;
    const assists = playerData.assists || 0;
    const rebounds = playerData.rebounds || 0;
    const steals = playerData.steals || 0;
    const blocks = playerData.blocks || 0;
    const turnovers = playerData.turnovers || 0;
    const fouls = playerData.personalFouls || 0;
    const minutes = playerData.minutesPlayed || 1;
    
    const per = ((points + assists + rebounds + steals + blocks) - (turnovers + fouls)) / minutes * 48;
    return Math.max(0, per);
  }
  
  private static calculateWinShares(playerData: any): number {
    // Simplified win shares calculation
    const impact = this.calculateOffensiveImpact(playerData) + this.calculateDefensiveImpact(playerData);
    const minutes = playerData.minutesPlayed || 0;
    return Math.max(0, impact * minutes / 2000);
  }
  
  private static calculateBPM(playerData: any): number {
    // Simplified BPM calculation
    return this.calculateOffensiveImpact(playerData) + this.calculateDefensiveImpact(playerData);
  }
  
  private static calculateVORP(playerData: any): number {
    // Simplified VORP calculation
    const bpm = this.calculateBPM(playerData);
    const minutes = playerData.minutesPlayed || 0;
    return Math.max(0, bpm * minutes / 2000);
  }
  
  private static calculateContextualMetrics(playerData: any, leagueContext: any): any {
    return {
      clutch: this.calculateClutchPerformance(playerData),
      playoff: this.calculatePlayoffPerformance(playerData),
      durability: this.calculateDurability(playerData),
      versatility: this.calculateVersatility(playerData)
    };
  }
  
  private static calculateClutchPerformance(playerData: any): number {
    // Simplified clutch calculation
    return (playerData.clutchPoints || 0) * 0.1 + (playerData.clutchShooting || 0.45) * 100;
  }
  
  private static calculatePlayoffPerformance(playerData: any): number {
    // Simplified playoff performance
    return (playerData.playoffPER || 15) / 15 * 100;
  }
  
  private static calculateDurability(playerData: any): number {
    const gamesPlayed = playerData.gamesPlayed || 0;
    const minutesPlayed = playerData.minutesPlayed || 0;
    const age = playerData.age || 25;
    
    const gameScore = Math.min(100, gamesPlayed / 82 * 100);
    const minuteScore = Math.min(100, minutesPlayed / 2500 * 100);
    const ageAdjustment = Math.max(0.5, (35 - age) / 10);
    
    return (gameScore + minuteScore) / 2 * ageAdjustment;
  }
  
  private static calculateVersatility(playerData: any): number {
    // Simplified versatility calculation based on position flexibility
    const positions = playerData.positions || [playerData.position];
    const positionScore = Math.min(100, positions.length * 25);
    
    const skillBalance = this.calculateSkillBalance(playerData);
    
    return (positionScore + skillBalance) / 2;
  }
  
  private static calculateSkillBalance(playerData: any): number {
    const shooting = this.calculateShootingScore(playerData);
    const playmaking = this.calculatePlaymakingScore(playerData);
    const rebounding = this.calculateReboundingScore(playerData);
    const defense = this.calculateDefenseScore(playerData);
    
    const skills = [shooting, playmaking, rebounding, defense];
    const average = skills.reduce((sum, skill) => sum + skill, 0) / skills.length;
    const variance = skills.reduce((sum, skill) => sum + Math.pow(skill - average, 2), 0) / skills.length;
    
    // Lower variance means more balanced skills
    return Math.max(0, 100 - variance / 10);
  }
  
  private static calculateMarketValue(playerData: any, impactMetrics: any, leagueContext: any): any {
    const baseValue = Math.max(1, impactMetrics.total * 5);
    const ageAdjustment = this.getAgeAdjustment(playerData.age || 25);
    const positionAdjustment = this.getPositionValueAdjustment(playerData.position);
    
    const estimatedValue = baseValue * ageAdjustment * positionAdjustment;
    const currentSalary = playerData.salary || estimatedValue;
    const efficiency = estimatedValue / currentSalary;
    
    return {
      estimated: Math.round(estimatedValue * 100) / 100,
      efficiency: Math.round(efficiency * 100) / 100,
      trade: Math.round(estimatedValue * 0.8 * 100) / 100
    };
  }
  
  private static calculateProjections(playerData: any, impactMetrics: any): any {
    const age = playerData.age || 25;
    const currentImpact = impactMetrics.total;
    
    let trajectory: 'ascending' | 'peak' | 'declining';
    let projectedGrowth: number;
    let peakAge: number;
    
    if (age < 24) {
      trajectory = 'ascending';
      projectedGrowth = Math.max(0, (27 - age) * 0.1);
      peakAge = 27;
    } else if (age < 30) {
      trajectory = 'peak';
      projectedGrowth = Math.max(-0.1, (28 - age) * 0.05);
      peakAge = age;
    } else {
      trajectory = 'declining';
      projectedGrowth = Math.min(0, (30 - age) * 0.05);
      peakAge = Math.max(age - 2, 28);
    }
    
    return {
      growth: Math.round(projectedGrowth * 100) / 100,
      peakAge,
      trajectory
    };
  }
  
  private static calculateRiskFactors(playerData: any, leagueContext: any): any {
    const age = playerData.age || 25;
    const injuryHistory = playerData.injuryHistory || 0;
    const minutesPlayed = playerData.minutesPlayed || 0;
    const performanceVariance = playerData.performanceVariance || 0.1;
    
    const injuryRisk = Math.min(100, injuryHistory * 20 + Math.max(0, age - 30) * 5);
    const ageRisk = Math.max(0, (age - 25) * 3);
    const volatility = Math.min(100, performanceVariance * 500);
    
    return {
      injury: Math.round(injuryRisk),
      age: Math.round(ageRisk),
      volatility: Math.round(volatility)
    };
  }
  
  private static calculateOverallEvaluation(impactMetrics: any, skillGrades: any, advancedMetrics: any, contextualMetrics: any): any {
    const impactScore = Math.min(100, Math.max(0, (impactMetrics.total + 10) * 5));
    const skillScore = (skillGrades.shooting.score + skillGrades.playmaking.score + skillGrades.rebounding.score + skillGrades.defense.score + skillGrades.athleticism.score) / 5;
    const advancedScore = Math.min(100, Math.max(0, (advancedMetrics.per - 10) * 5));
    const contextScore = (contextualMetrics.clutch + contextualMetrics.durability + contextualMetrics.versatility) / 3;
    
    const overallScore = (impactScore * 0.4 + skillScore * 0.3 + advancedScore * 0.2 + contextScore * 0.1);
    
    let grade: string;
    if (overallScore >= 95) grade = 'A+';
    else if (overallScore >= 90) grade = 'A';
    else if (overallScore >= 85) grade = 'A-';
    else if (overallScore >= 80) grade = 'B+';
    else if (overallScore >= 75) grade = 'B';
    else if (overallScore >= 70) grade = 'B-';
    else if (overallScore >= 65) grade = 'C+';
    else if (overallScore >= 60) grade = 'C';
    else if (overallScore >= 55) grade = 'C-';
    else if (overallScore >= 50) grade = 'D+';
    else if (overallScore >= 45) grade = 'D';
    else if (overallScore >= 40) grade = 'D-';
    else grade = 'F';
    
    return {
      score: Math.round(overallScore),
      grade
    };
  }
  
  private static findSimilarPlayers(playerData: any, leagueContext: any): string[] {
    // Simplified similar player finding
    return ['Player A', 'Player B', 'Player C'];
  }
  
  private static findHistoricalComparisons(playerData: any, leagueContext: any): string[] {
    // Simplified historical comparison
    return ['Historical Player A', 'Historical Player B'];
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
  
  private static getAgeAdjustment(age: number): number {
    if (age < 22) return 1.2;
    if (age < 25) return 1.1;
    if (age < 28) return 1.0;
    if (age < 32) return 0.9;
    return 0.7;
  }
  
  private static getPositionValueAdjustment(position: string): number {
    const adjustments: Record<string, number> = {
      'PG': 1.1,
      'SG': 1.0,
      'SF': 1.05,
      'PF': 0.95,
      'C': 0.9
    };
    return adjustments[position] || 1.0;
  }
}
