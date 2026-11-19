"use client";

import { useRouter } from "next/navigation";
import { BriefsLibrary } from "../../components/BriefsLibrary";

export default function BriefsPage() {
  const router = useRouter();
  return <BriefsLibrary onOpenBoard={(id) => router.push(`/?tab=boards&board=${encodeURIComponent(id)}`)} />;
}
