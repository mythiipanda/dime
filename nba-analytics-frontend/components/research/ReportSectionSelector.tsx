"use client";

import React from 'react';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { BotMessageSquare } from 'lucide-react';

interface ReportSection {
  id: string;
  label: string;
}

interface ReportSectionSelectorProps {
  reportSections: ReportSection[];
  selectedSections: string[];
  onSectionChange: (sectionId: string, checked: boolean) => void;
  isLoading: boolean;
}

export function ReportSectionSelector({
  reportSections,
  selectedSections,
  onSectionChange,
  isLoading,
}: ReportSectionSelectorProps) {
  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button variant="outline" className="w-full justify-between" disabled={isLoading}>
          Customize Report Sections
          <BotMessageSquare className="h-4 w-4" />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="mt-4 p-4 border rounded-md">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {reportSections.map((section) => (
            <div key={section.id} className="flex items-center space-x-2">
              <Checkbox
                id={section.id}
                checked={selectedSections.includes(section.id)}
                onCheckedChange={(checked) => onSectionChange(section.id, !!checked)}
                disabled={isLoading}
              />
              <Label htmlFor={section.id} className="text-sm font-normal">
                {section.label}
              </Label>
            </div>
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
} 