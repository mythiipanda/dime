"use client"

import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Card, CardContent, CardHeader } from "@/components/ui/card"

export function TableSkeleton() {
  return (
    <div className="rounded-md border animate-in fade-in-0 duration-300">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12"><Skeleton className="h-4 w-8" /></TableHead>
            <TableHead className="min-w-[200px]"><Skeleton className="h-4 w-32" /></TableHead>
            <TableHead className="w-[60px]"><Skeleton className="h-4 w-8" /></TableHead>
            <TableHead className="w-[60px]"><Skeleton className="h-4 w-8" /></TableHead>
            <TableHead className="w-[80px]"><Skeleton className="h-4 w-12" /></TableHead>
            <TableHead className="w-[60px]"><Skeleton className="h-4 w-8" /></TableHead>
            <TableHead className="w-[100px]"><Skeleton className="h-4 w-16" /></TableHead>
            <TableHead className="w-[80px]"><Skeleton className="h-4 w-12" /></TableHead>
            <TableHead className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableHead>
            <TableHead className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableHead>
            <TableHead className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array(15).fill(0).map((_, i) => (
            <TableRow key={i}>
              <TableCell><Skeleton className="h-4 w-8" /></TableCell>
              <TableCell><Skeleton className="h-4 w-32" /></TableCell>
              <TableCell><Skeleton className="h-4 w-8" /></TableCell>
              <TableCell><Skeleton className="h-4 w-8" /></TableCell>
              <TableCell><Skeleton className="h-4 w-12" /></TableCell>
              <TableCell><Skeleton className="h-4 w-8" /></TableCell>
              <TableCell><Skeleton className="h-4 w-16" /></TableCell>
              <TableCell><Skeleton className="h-4 w-12" /></TableCell>
              <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableCell>
              <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableCell>
              <TableCell className="hidden md:table-cell"><Skeleton className="h-4 w-16" /></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export function CardSkeleton() {
  return (
    <Card className="animate-in fade-in-0 duration-300">
      <CardHeader>
        <Skeleton className="h-6 w-[180px]" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-[80%]" />
        <Skeleton className="h-4 w-[60%]" />
      </CardContent>
    </Card>
  )
}