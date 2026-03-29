import { cn } from "@/lib/utils";
import type { EvalMetricScores } from "../../types/eval";

interface DifficultyChartProps {
  perDifficulty: Record<string, EvalMetricScores> | undefined;
}

const DIFFICULTIES = ["Simple", "Medium", "Complex", "Calculation"] as const;
const METRICS: { key: keyof EvalMetricScores; label: string; color: string }[] = [
  { key: "context_precision", label: "Precision", color: "bg-blue-500" },
  { key: "context_recall", label: "Recall", color: "bg-purple-500" },
  { key: "answer_faithfulness", label: "Faithfulness", color: "bg-green-500" },
  { key: "answer_relevance", label: "Relevance", color: "bg-orange-500" },
];

function Bar({ score, color }: { score: number | null; color: string }) {
  const pct = score !== null ? Math.round(score * 100) : 0;
  return (
    <div className="flex items-center gap-1 h-4">
      <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-muted-foreground tabular-nums w-8">
        {score !== null ? score.toFixed(2) : "—"}
      </span>
    </div>
  );
}

export function DifficultyChart({ perDifficulty }: DifficultyChartProps) {
  if (!perDifficulty) return null;

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {DIFFICULTIES.map((diff) => {
        const scores = perDifficulty[diff];
        if (!scores) return null;
        return (
          <div key={diff} className="rounded-lg border border-border bg-card p-3 flex flex-col gap-2">
            <p className="text-xs font-semibold text-foreground">{diff}</p>
            {METRICS.map(({ key, label, color }) => (
              <div key={key}>
                <p className="text-[10px] text-muted-foreground mb-0.5">{label}</p>
                <Bar score={scores[key]} color={color} />
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
