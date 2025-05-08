"use client";

import * as React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";

export default function ShotChartsPage() {
  return (
    <div className="flex flex-col space-y-6 flex-1">
      <Card className="flex-1">
        <CardHeader>
          <CardTitle>Shot Charts</CardTitle>
          <CardDescription>Visualize player shooting patterns and efficiency.</CardDescription>
        </CardHeader>
        <CardContent className="flex items-center justify-center h-full">
          <p className="text-muted-foreground">Shot chart visualizations will be available here soon.</p>
        </CardContent>
      </Card>
    </div>
  );
}
