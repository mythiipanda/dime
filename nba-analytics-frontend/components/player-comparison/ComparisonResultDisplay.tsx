`use client`;

import { Loader2, AlertCircle, ImageOff } from 'lucide-react';
import Image from 'next/image'; // Using next/image for optimized image handling
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface ComparisonResultDisplayProps {
  isLoading: boolean;
  comparisonImage: string | null; // Base64 encoded image string
  error: string | null;
}

export function ComparisonResultDisplay({
  isLoading,
  comparisonImage,
  error,
}: ComparisonResultDisplayProps) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-muted-foreground">
        <Loader2 className="h-12 w-12 animate-spin mb-4 text-primary" />
        <p className="text-lg font-medium">Generating Comparison Chart...</p>
        <p className="text-sm">This might take a moment.</p>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive" className="max-w-md mx-auto">
        <AlertCircle className="h-5 w-5" />
        <AlertTitle>Error Generating Comparison</AlertTitle>
        <AlertDescription>
          {error}
          <p className='mt-2 text-xs'>Please try adjusting your selections or try again later.</p>
        </AlertDescription>
      </Alert>
    );
  }

  if (comparisonImage) {
    return (
      <div className="border rounded-lg overflow-hidden shadow-lg bg-card">
        <Image
          src={`data:image/png;base64,${comparisonImage}`}
          alt="Player Shot Comparison Chart"
          width={1200} // Provide appropriate dimensions or use layout="responsive"
          height={800}
          style={{ width: '100%', height: 'auto' }} // Ensure responsiveness
          priority // Consider if this image is LCP
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center h-64 border-2 border-dashed rounded-lg bg-muted/50">
      <ImageOff className="h-16 w-16 text-muted-foreground mb-4 opacity-50" />
      <p className="text-lg font-medium text-muted-foreground">No Comparison Generated Yet</p>
      <p className="text-sm text-muted-foreground">Select players and options, then click "Generate Comparison".</p>
    </div>
  );
} 