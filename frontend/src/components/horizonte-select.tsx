"use client";

import { useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const OPTIONS = [6, 12, 24];

export function HorizonteSelect({ horizonte }: { horizonte: number }) {
  const router = useRouter();

  return (
    <Select
      value={String(horizonte)}
      onValueChange={(value) => router.push(`/projecoes?horizonte=${value}`)}
    >
      <SelectTrigger className="w-[140px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {OPTIONS.map((h) => (
          <SelectItem key={h} value={String(h)}>
            {h} meses
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
