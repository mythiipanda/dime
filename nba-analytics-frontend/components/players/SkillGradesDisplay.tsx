`use client`;

import { SkillGrades } from "@/app/(app)/players/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

interface SkillGradesDisplayProps {
  grades: SkillGrades;
}

const gradeColorMapping: { [key: string]: string } = {
  "A+": "bg-green-500 hover:bg-green-600 text-white",
  "A": "bg-green-400 hover:bg-green-500 text-white",
  "A-": "bg-green-300 hover:bg-green-400 text-green-900",
  "B+": "bg-lime-400 hover:bg-lime-500 text-lime-900",
  "B": "bg-lime-300 hover:bg-lime-400 text-lime-900",
  "B-": "bg-lime-200 hover:bg-lime-300 text-lime-800",
  "C+": "bg-yellow-300 hover:bg-yellow-400 text-yellow-900",
  "C": "bg-yellow-200 hover:bg-yellow-300 text-yellow-800",
  "C-": "bg-yellow-100 hover:bg-yellow-200 text-yellow-700",
  "D+": "bg-orange-300 hover:bg-orange-400 text-orange-900",
  "D": "bg-orange-200 hover:bg-orange-300 text-orange-800",
  "D-": "bg-orange-100 hover:bg-orange-200 text-orange-700",
  "F": "bg-red-400 hover:bg-red-500 text-white",
};

const skillLabels: { [key in keyof SkillGrades]-?: string } = {
  perimeter_shooting: "Perimeter Shooting",
  interior_scoring: "Interior Scoring",
  playmaking: "Playmaking",
  perimeter_defense: "Perimeter Defense",
  interior_defense: "Interior Defense",
  rebounding: "Rebounding",
  off_ball_movement: "Off-Ball Movement",
  hustle: "Hustle",
  versatility: "Versatility",
};

export function SkillGradesDisplay({ grades }: SkillGradesDisplayProps) {
  if (!grades || Object.keys(grades).length === 0) {
    return <p className="text-sm text-muted-foreground">Skill grades data is not available.</p>;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">Skill Grades</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(Object.keys(grades) as Array<keyof SkillGrades>).map((key) => {
            const gradeValue = grades[key];
            if (!gradeValue) return null;
            const label = skillLabels[key] || key.replace(/_/g, ' ').split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            const badgeColor = gradeColorMapping[gradeValue] || "bg-gray-300 hover:bg-gray-400 text-gray-800";

            return (
              <div key={key} className="p-3 bg-muted/50 rounded-lg flex justify-between items-center">
                <span className="text-sm font-medium text-foreground mr-2">{label}:</span>
                <Badge className={`text-xs font-semibold px-2.5 py-1 ${badgeColor}`}>{gradeValue}</Badge>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
} 