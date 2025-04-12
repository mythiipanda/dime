"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, Send, Brain, TrendingUp, Activity, Trophy } from "lucide-react";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function AIAssistantPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      // TODO: Implement actual API call here
      const response = await new Promise((resolve) => 
        setTimeout(() => resolve({ content: "This is a sample response from the AI assistant." }), 1000)
      );
      
      const assistantMessage: Message = { 
        role: "assistant", 
        content: (response as any).content 
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error("Error:", error);
      const errorMessage: Message = { 
        role: "assistant", 
        content: "Sorry, I encountered an error. Please try again." 
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExampleClick = (query: string) => {
    setInput(query);
  };

  const categories = [
    {
      title: "Player Analysis",
      icon: Brain,
      queries: [
        "Compare LeBron James and Kevin Durant's stats this season",
        "Show me Steph Curry's shooting percentages",
        "Who are the top 3-point shooters this year?"
      ]
    },
    {
      title: "Team Performance",
      icon: TrendingUp,
      queries: [
        "Which team has the best defensive rating?",
        "Compare Lakers vs Warriors head-to-head",
        "Show me the Celtics' win streak"
      ]
    },
    {
      title: "Game Analysis",
      icon: Activity,
      queries: [
        "Analyze last night's Bucks vs Nets game",
        "What were the key factors in the Heat's victory?",
        "Show me clutch time statistics"
      ]
    },
    {
      title: "League Leaders",
      icon: Trophy,
      queries: [
        "Who leads the NBA in assists?",
        "Show me the top 5 scorers",
        "Who has the most double-doubles?"
      ]
    }
  ];

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-background">
      <div className="flex-1 container py-6 space-y-6 overflow-hidden">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold tracking-tight">Dime Assistant</h1>
          <p className="text-muted-foreground">
            Your AI-powered NBA research companion. Ask questions about players, teams, and games to get instant insights.
          </p>
        </div>

        {messages.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {categories.map((category) => (
              <Card key={category.title} className="bg-card hover:bg-card/80 transition-colors">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {<category.icon className="h-5 w-5" />}
                    {category.title}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {category.queries.map((query) => (
                    <Button
                      key={query}
                      variant="ghost"
                      className="w-full justify-start text-left h-auto whitespace-normal"
                      onClick={() => handleExampleClick(query)}
                    >
                      {query}
                    </Button>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <ScrollArea className="flex-1 pr-4 -mr-4">
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={cn(
                    "flex w-full",
                    message.role === "assistant" ? "justify-start" : "justify-end"
                  )}
                >
                  <div
                    className={cn(
                      "rounded-lg px-4 py-2 max-w-[80%]",
                      message.role === "assistant"
                        ? "bg-muted text-foreground"
                        : "bg-primary text-primary-foreground"
                    )}
                  >
                    {message.content}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        )}
      </div>

      <div className="border-t bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <form onSubmit={handleSubmit} className="container flex gap-2 py-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Ask about players, teams, stats, or game analysis..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="pl-9"
            />
          </div>
          <Button type="submit" disabled={isLoading}>
            {isLoading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-background border-t-foreground" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            <span className="ml-2">Ask</span>
          </Button>
        </form>
      </div>
    </div>
  );
} 