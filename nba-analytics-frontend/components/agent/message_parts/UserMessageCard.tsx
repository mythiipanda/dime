"use client";

import React from 'react';
import { Card } from "@/components/ui/card";
import ReactMarkdown, { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface UserMessageCardProps {
  content: string;
  markdownComponents: Components;
}

const UserMessageCard: React.FC<UserMessageCardProps> = ({ content, markdownComponents }) => {
  return (
    <Card className="prose prose-sm dark:prose-invert max-w-full rounded-xl bg-primary text-primary-foreground p-3 shadow-md break-words">
      <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>{content || ''}</ReactMarkdown>
    </Card>
  );
};

export default UserMessageCard; 