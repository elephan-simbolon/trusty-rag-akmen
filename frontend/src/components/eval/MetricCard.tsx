import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  score: number | null;
  description: string;
}

function scoreColor(score: number | null): string {
  if (score === null) return "text-muted-foreground";
  if (score >= 0.8) return "text-green-600 dark:text-green-400";
  if (score >= 0.6) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function barColor(score: number | null): string {
  if (score === null) return "bg-muted";
  if (score >= 0.8) return "bg-green-500";
  if (score >= 0.6) return "bg-yellow-500";
  return "bg-red-500";
}

export function MetricCard({ label, score, description }: MetricCardProps) {
  const pct = score !== null ? Math.round(score * 100) : 0;

  return (
    <div className="rounded-lg border border-border bg-card p-4 flex flex-col gap-2">
      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
        {label}
      </p>
      <p className={cn("text-3xl font-bold tabular-nums", scoreColor(score))}>
        {score !== null ? score.toFixed(2) : "—"}
      </p>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={cn("h-full rounded-full transition-all", barColor(score))}
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground">{description}</p>
    </div>
  );
}
