"use client";

import { useRouter } from "next/navigation";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export function MonthSelect({
  months,
  selected,
  monthLabels,
}: {
  months: string[];
  selected: string | null;
  monthLabels: Record<string, string>;
}) {
  const router = useRouter();

  return (
    <Select
      value={selected ?? "todos"}
      onValueChange={(value) => {
        router.push(value === "todos" ? "/dashboard" : `/dashboard?month=${value}`);
      }}
    >
      <SelectTrigger className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="todos">Todos os meses</SelectItem>
        {[...months].reverse().map((m) => (
          <SelectItem key={m} value={m}>
            {monthLabels[m] ?? m}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
