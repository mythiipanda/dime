// nba-analytics-frontend/lib/utils/teams.ts

// Formatting utilities for team standings display

export function formatRecord(wins: number, losses: number): string {
  return `${wins}-${losses}`;
}

export function formatWinPct(pct: number): string {
  const numPct = Number(pct);
  if (isNaN(numPct)) {
    return 'N/A';
  }
  return (numPct * 100).toFixed(1);
}

export function getGamesBehind(gb: number): string {
  const numGb = Number(gb);
  if (isNaN(numGb) || numGb === 0) return '-';
  return numGb.toFixed(1);
}

export function getRecordColor(wins: number, losses: number): string {
  const totalGames = wins + losses;
  if (totalGames === 0) return 'text-gray-500';

  const winPct = wins / totalGames;
  if (winPct >= 0.6) return 'text-green-500';
  if (winPct <= 0.4) return 'text-red-500';
  return 'text-yellow-500'; // Consider a neutral default like text-foreground?
}

export function formatStreak(streak: string): string {
  return String(streak || '').trim();
}

/**
 * Parses clinch indicators like "x", "y-cen", "pi" into human-readable strings.
 * @param indicator The raw clinch indicator string (e.g., "x", "y", "p-sw", "o")
 * @returns An array of readable clinch descriptions.
 */
export function getClinchIndicators(indicator?: string): string[] {
  if (!indicator || typeof indicator !== 'string') return [];

  const parts = indicator
    .trim()
    .replace(/^[\s*-]+/, '')
    .split('-')
    .map(s => s.trim().toLowerCase())
    .filter(i => i);

  if (parts.length === 0) return [];

  const descriptions = parts.map(i => {
    switch(i) {
      case 'x': return 'Clinched Playoff Spot';
      case 'y': return 'Clinched Division Title'; 
      case 'z': return 'Clinched Conference Best Record';
      case '*': return 'Clinched Conference Best Record';
      case 'w': return 'Clinched Conference/Division';
      case 'p': return 'Clinched Play-In Spot'; // 'p' alone usually means play-in
      case 'pi': return 'Clinched Play-In Spot';
      case 'e': return 'Clinched Conference/Division';
      case 'o': return 'Eliminated from Contention';
      case 'a': case 'atl': return 'Clinched Atlantic Division';
      case 'c': case 'cen': return 'Clinched Central Division';
      case 'se': return 'Clinched Southeast Division';
      case 'nw': return 'Clinched Northwest Division';
      case 'pac': return 'Clinched Pacific Division';
      case 'sw': return 'Clinched Southwest Division';
      default:
          console.warn(`Unknown clinch indicator part: '${i}' in full indicator '${indicator}'`);
          return `Unknown (${i})`;
    }
  });
  
  // Remove duplicates (e.g., if '*' and 'z' both map to the same string)
  return Array.from(new Set(descriptions));
} 