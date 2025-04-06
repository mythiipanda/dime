// components/agent/ChatMessageDisplay.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from "@/components/ui/card";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"; // Import Avatar components
import { UserIcon, BotIcon } from "lucide-react"; // Import icons for avatars
import { ChatMessage } from '@/lib/hooks/useAgentChatSSE'; // Import the interface from the new hook file

interface ChatMessageDisplayProps {
  message: ChatMessage;
}

export function ChatMessageDisplay({ message }: ChatMessageDisplayProps) {
  return (
    <div className={`flex items-start gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      {/* Assistant Avatar */}
      {message.role === 'assistant' && (
        <Avatar className="h-8 w-8 border">
          <AvatarFallback><BotIcon className="h-4 w-4" /></AvatarFallback>
        </Avatar>
      )}
      {/* Message Card */}
      <Card className={`max-w-[75%] ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
        <CardContent className="p-2"> {/* Removed max-height/overflow */}
          {message.role === 'assistant' ? (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              {/* Render markdown for assistant messages */}
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : (
            // Render plain text for user messages
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