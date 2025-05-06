"use client"

import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"
import { useRouter } from "next/navigation"

interface ErrorBoundaryProps {
  error: Error
  reset?: () => void
}

export function ErrorBoundaryHandler({ error, reset }: ErrorBoundaryProps) {
  const router = useRouter()

  const handleReset = () => {
    if (reset) {
      reset()
    } else {
      router.refresh()
    }
  }

  return (
    <div className="flex h-[50vh] items-center justify-center px-4 animate-in fade-in-0 duration-500">
      <Alert variant="destructive" className="max-w-2xl"> {/* Alert already has its own entrance animation */}
        <AlertCircle className="h-6 w-6" />
        <AlertTitle className="text-lg font-semibold">
          Something went wrong
        </AlertTitle>
        <AlertDescription className="mt-2 flex flex-col gap-4">
          <p>{error.message || "An error occurred while loading the data."}</p>
          <Button 
            variant="outline" 
            onClick={handleReset}
            className="w-fit"
          >
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    </div>
  )
}