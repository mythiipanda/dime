export type WorkflowValues = Record<string, string>;
export interface WorkflowField {
  id: string;
  label: string;
  kind: "team" | "player" | "text" | "select";
  options?: readonly string[];
  placeholder: string;
  required: boolean;
}
export interface Workflow {
  id: string;
  title: string;
  summary: string;
  category: "Game prep" | "Roster" | "Player evaluation";
  deliverable: readonly string[];
  fields: readonly WorkflowField[];
  buildRequest: (values: WorkflowValues) => string;
}

const field = (id: string, label: string, kind: WorkflowField["kind"], placeholder: string, options?: readonly string[], required = true): WorkflowField =>
  ({ id, label, kind, placeholder, options, required });

function defineWorkflow(spec: Omit<Workflow, "buildRequest">): Workflow {
  return {
    ...spec,
    buildRequest: (values) => [
      `Prepare a ${spec.title.toLowerCase()}.`,
      ...spec.fields.flatMap((f) => values[f.id]?.trim() ? [`${f.label}: ${values[f.id].trim()}`] : []),
      "Use the 2025-26 season unless explicitly stated otherwise. Source all numbers from the warehouse and include citations. Explicitly state when data is missing instead of guessing.",
      "Return these deliverable sections in this order:",
      ...spec.deliverable.map((section, i) => `${i + 1}. ${section}`),
    ].join("\n"),
  };
}

export const workflows: readonly Workflow[] = [
  defineWorkflow({ id: "opponent-scouting", title: "Opponent scouting report", summary: "Find the matchup edges and turn them into a game plan.", category: "Game prep", deliverable: ["Matchup overview", "Opponent strengths and weaknesses", "Key matchups", "Recommended game plan", "Data gaps"], fields: [field("team", "Your team", "team", "Select your team"), field("opponent", "Opponent", "team", "Select opponent")] }),
  defineWorkflow({ id: "lineup-audit", title: "Lineup audit", summary: "Separate reliable combinations from small-sample noise.", category: "Roster", deliverable: ["Rotation overview", "Lineup performance", "Recommended combinations", "Sample limitations"], fields: [field("team", "Team", "team", "Select team"), field("minutes", "Minimum minutes", "select", "Select minimum minutes", ["50", "100", "200", "500"])] }),
  defineWorkflow({ id: "trade-evaluation", title: "Trade evaluation", summary: "Assess the basketball fit and cost for both sides.", category: "Roster", deliverable: ["Trade overview", "Team A impact", "Team B impact", "Salary and feasibility", "Recommendation", "Data gaps"], fields: [field("teamA", "Team A", "team", "Select team A"), field("playersOut", "Players out of team A", "player", "Names, separated by commas"), field("teamB", "Team B", "team", "Select team B"), field("playersIn", "Players into team A", "player", "Names, separated by commas")] }),
  defineWorkflow({ id: "target-shortlist", title: "Target shortlist", summary: "Build an evidence-led list around a specific roster need.", category: "Roster", deliverable: ["Roster need", "Ranked targets", "Fit and trade-offs", "Salary considerations", "Data gaps"], fields: [field("team", "Team", "team", "Select team"), field("need", "Roster need", "select", "Select need", ["rim protector", "3-and-D wing", "primary creator", "backup point guard", "stretch big"]), field("salary", "Maximum 2026-27 salary", "text", "e.g. $20 million", undefined, false)] }),
  defineWorkflow({ id: "player-evaluation", title: "Player evaluation", summary: "Understand a player’s production, role and limitations.", category: "Player evaluation", deliverable: ["Player profile", "Offensive impact", "Defensive impact", "Role and recommendation", "Data gaps"], fields: [field("player", "Player", "player", "Enter player name")] }),
  defineWorkflow({ id: "player-comparison", title: "Player comparison", summary: "Compare two players through the same decision-making lens.", category: "Player evaluation", deliverable: ["Side-by-side overview", "Offensive comparison", "Defensive comparison", "Role and fit", "Recommendation", "Data gaps"], fields: [field("playerA", "Player A", "player", "Enter first player"), field("playerB", "Player B", "player", "Enter second player")] }),
];

export function validateWorkflow(workflow: Workflow, values: WorkflowValues): WorkflowField[] {
  return workflow.fields.filter((f) => f.required && !values[f.id]?.trim());
}
