// components/agent/ChatMessageDisplay.tsx
"use client"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"
import { UserIcon, BotIcon } from "lucide-react"

interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

interface ChatMessageDisplayProps {
  message: ChatMessage
}

export function ChatMessageDisplay({ message }: ChatMessageDisplayProps) {
  const isUser = message.role === "user"

  return (
    <div
      className={cn(
        "flex w-full gap-3 p-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <Avatar className={cn("h-8 w-8", isUser ? "bg-primary" : "bg-muted")}>
        {isUser ? (
          <>
            <AvatarImage src="/placeholder-user.jpg" alt="User" />
            <AvatarFallback>
              <UserIcon className="h-4 w-4" />
            </AvatarFallback>
          </>
        ) : (
          <>
            <AvatarImage src="/nba-logo.png" alt="NBA Assistant" />
            <AvatarFallback>
              <BotIcon className="h-4 w-4" />
            </AvatarFallback>
          </>
        )}
      </Avatar>

      <div className={cn("flex max-w-[80%] flex-col gap-2", isUser ? "items-end" : "items-start")}>
        <Card
          className={cn(
            "rounded-2xl px-4 py-3",
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted"
          )}
        >
          <div className="prose prose-sm dark:prose-invert font-regular prose-strong:font-semibold prose-code:font-regular"> {/* Typography: Base regular, strong semibold, code regular */}
            {/* Format message content based on type */}
            {message.content.includes("```") ? (
              // Handle code blocks
              message.content.split("```").map((part, index) => {
                if (index % 2 === 1) {
                  // Code block
                  return (
                    <pre key={index} className="bg-secondary p-2 rounded-md overflow-x-auto">
                      <code>{part.trim()}</code>
                    </pre>
                  )
                }
                // Regular text
                return <p key={index}>{part}</p>
              })
            ) : message.content.includes("table:") ? (
              // Handle table data
              <div className="overflow-x-auto">
                <pre className="text-sm">{message.content}</pre> {/* Typography: text-sm */}
              </div>
            ) : (
              // Regular text
              <p className="whitespace-pre-wrap">{message.content}</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}