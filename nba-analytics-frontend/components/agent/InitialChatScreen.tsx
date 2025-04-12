"use client"

// components/agent/InitialChatScreen.tsx
// Removed unused Card components
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { 
  BarChart3Icon, 
  CalendarIcon, 
  TrendingUpIcon,
  UserIcon,
  UsersIcon,
  StarIcon,
  TrophyIcon
} from "lucide-react"
import { PromptInputForm } from "./PromptInputForm"

const EXAMPLE_PROMPTS = [
  {
    category: "Player Analysis",
    icon: <UserIcon className="h-4 w-4" />,
    prompts: [
      "Show me LeBron James's stats for this season",
      "Compare Stephen Curry and Luka Doncic's shooting percentages",
      "Who has the most triple-doubles this season?"
    ]
  },
  {
    category: "Team Performance",
    icon: <UsersIcon className="h-4 w-4" />,
    prompts: [
      "Compare the Lakers and Celtics this season",
      "Which team has the best defensive rating?",
      "Show me the Nuggets' last 10 games"
    ]
  },
  {
    category: "Game Analysis",
    icon: <BarChart3Icon className="h-4 w-4" />,
    prompts: [
      "What are the predictions for tonight's games?",
      "Show me the box score from last night's Bucks game",
      "What was the highest scoring game this season?"
    ]
  },
  {
    category: "League Leaders",
    icon: <TrophyIcon className="h-4 w-4" />,
    prompts: [
      "Who are the top 5 scorers this season?",
      "Show me the MVP race standings",
      "Which team has the best record in the East?"
    ]
  }
]

interface InitialChatScreenProps {
  onExampleClick: (prompt: string) => void
  onSubmit: (prompt: string) => void
  isLoading?: boolean
}

export function InitialChatScreen({ onExampleClick, onSubmit, isLoading }: InitialChatScreenProps) {
  return (
    <div className="space-y-6">
      {/* Welcome Section */}
      <div className="text-center space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome to Dime</h1> {/* Typography: font-semibold (Size 1) */}
        <p className="text-muted-foreground">
          Your AI-powered NBA research companion. Ask questions about players, teams, and games to get instant insights.
        </p>
      </div>

      {/* Prompt Input Form */}
      <div className="max-w-3xl mx-auto">
        <PromptInputForm 
          onSubmit={onSubmit}
          isLoading={isLoading}
          className="shadow-lg"
        />
      </div>

      {/* Example Categories */}
      <div className="grid gap-4 md:grid-cols-2">
        {EXAMPLE_PROMPTS.map((category) => (
          <Card key={category.category}>
            <CardHeader className="space-y-1">
              <CardTitle className="text-xl flex items-center gap-2"> {/* Typography: text-xl (Size 2) */}
                {category.icon}
                {category.category}
              </CardTitle>
              <CardDescription>
                Click any example to start analyzing
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {category.prompts.map((prompt) => (
                <Button
                  key={prompt}
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => onExampleClick(prompt)}
                >
                  <StarIcon className="mr-2 h-3 w-3" />
                  {prompt}
                </Button>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Features Section */}
      <div className="grid gap-4 md:grid-cols-3">
        <div className="flex items-center gap-2 p-4 rounded-md border bg-card"> {/* Spacing: rounded-md */}
          <TrendingUpIcon className="h-8 w-8 text-primary" />
          <div>
            <h3 className="font-semibold">Real-time Stats</h3>
            <p className="text-sm text-muted-foreground">Up-to-date NBA statistics and analysis</p>
          </div>
        </div>
        <div className="flex items-center gap-2 p-4 rounded-md border bg-card"> {/* Spacing: rounded-md */}
          <BarChart3Icon className="h-8 w-8 text-primary" />
          <div>
            <h3 className="font-semibold">Deep Analysis</h3>
            <p className="text-sm text-muted-foreground">Advanced metrics and comparisons</p>
          </div>
        </div>
        <div className="flex items-center gap-2 p-4 rounded-md border bg-card"> {/* Spacing: rounded-md */}
          <CalendarIcon className="h-8 w-8 text-primary" />
          <div>
            <h3 className="font-semibold">Game Insights</h3>
            <p className="text-sm text-muted-foreground">Predictions and historical data</p>
          </div>
        </div>
      </div>
    </div>
  )
}