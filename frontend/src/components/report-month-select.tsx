"use client";

import { useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function ReportMonthSelect({
  months,
  selected,
  monthLabels,
}: {
  months: string[];
  selected: string;
  monthLabels: Record<string, string>;
}) {
  const router = useRouter();

  return (
    <Select
      value={selected}
      onValueChange={(value) => {
        if (!value) return;
        router.push(`/relatorio?month=${value}`);
      }}
    >
      <SelectTrigger className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {[...months].reverse().map((m) => (
          <SelectItem key={m} value={m}>
            {monthLabels[m] ?? m}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
