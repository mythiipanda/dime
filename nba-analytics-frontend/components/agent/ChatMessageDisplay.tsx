// components/agent/ChatMessageDisplay.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent } from "@/components/ui/card";
import { ChatMessage } from '@/lib/hooks/useAgentChatSSE'; // Import the interface from the new hook file

interface ChatMessageDisplayProps {
  message: ChatMessage;
}

export function ChatMessageDisplay({ message }: ChatMessageDisplayProps) {
  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <Card className={`max-w-[75%] ${message.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
        <CardContent className={`p-2 ${message.role === 'assistant' ? 'max-h-[60vh] overflow-y-auto' : ''}`}> {/* Reduced padding */}
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
    </div>
  );
}