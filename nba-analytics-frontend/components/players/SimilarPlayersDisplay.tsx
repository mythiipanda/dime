`use client`;

import { PlayerData } from "@/app/(app)/players/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import Link from "next/link";

interface SimilarPlayersDisplayProps {
  players: PlayerData['similar_players'];
}

export function SimilarPlayersDisplay({ players }: SimilarPlayersDisplayProps) {
  if (!players || players.length === 0) {
    return <p className="text-sm text-muted-foreground">Similar players data is not available.</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Similar Players</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Player Name</TableHead>
              <TableHead className="text-right">Similarity Score</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {players.map((player) => (
              <TableRow key={player.player_id}>
                <TableCell className="font-medium">
                  <Link href={`/players?query=${encodeURIComponent(player.player_name)}`} className="hover:underline text-blue-600 hover:text-blue-800">
                    {player.player_name}
                  </Link>
                </TableCell>
                <TableCell className="text-right">{(player.similarity_score * 100).toFixed(1)}%</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
} 