// components/agent/ChatMessageDisplay.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { UserIcon, BotIcon } from "lucide-react";
import clsx from 'clsx'; // Import clsx
import { ChatMessage } from '@/lib/hooks/useAgentChatSSE'; // Import the interface from the new hook file

interface ChatMessageDisplayProps {
  message: ChatMessage;
}

export function ChatMessageDisplay({ message }: ChatMessageDisplayProps) {
  // Rewriting the return statement to ensure correct syntax
  return (
    <div
      className={clsx(
        "flex items-start gap-3",
        message.role === 'user' ? 'justify-end' : 'justify-start'
      )}
    >
      {/* Assistant Avatar */}
      {message.role === 'assistant' && (
        <Avatar className="h-8 w-8 border">
          <AvatarFallback><BotIcon className="h-4 w-4" /></AvatarFallback>
        </Avatar>
      )}

      {/* Message Card */}
      <Card
        className={clsx(
          "max-w-[75%]",
          message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'
        )}
      >
        <CardContent className="p-2">
          {message.role === 'assistant' ? (
            <div
              className="prose prose-sm dark:prose-invert max-w-none"
              style={{ overflowWrap: 'break-word' }}
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          )}
        </CardContent>
      </Card>

      {/* User Avatar */}
      {message.role === 'user' && (
        <Avatar className="h-8 w-8 border">
          <AvatarFallback><UserIcon className="h-4 w-4" /></AvatarFallback>
        </Avatar>
      )}
    </div>
  );
}