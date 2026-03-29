import { useState } from "react";
import { cn } from "@/lib/utils";
import type { EvalQueryResult } from "../../types/eval";

interface QueryResultTableProps {
  results: EvalQueryResult[];
}

function ScoreCell({ score }: { score: number | null }) {
  const color =
    score === null
      ? "text-muted-foreground"
      : score >= 0.8
      ? "text-green-600 dark:text-green-400"
      : score >= 0.6
      ? "text-yellow-600 dark:text-yellow-400"
      : "text-red-600 dark:text-red-400";
  return (
    <td className={cn("px-3 py-2 text-sm tabular-nums text-right", color)}>
      {score !== null ? score.toFixed(2) : "—"}
    </td>
  );
}

const DIFFICULTIES = ["All", "Simple", "Medium", "Complex", "Calculation"] as const;

export function QueryResultTable({ results }: QueryResultTableProps) {
  const [filter, setFilter] = useState<string>("All");

  const filtered = filter === "All" ? results : results.filter((r) => r.difficulty === filter);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        {DIFFICULTIES.map((d) => (
          <button
            key={d}
            onClick={() => setFilter(d)}
            className={cn(
              "px-2.5 py-1 rounded-md text-xs font-medium transition-colors",
              filter === d
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            )}
          >
            {d}
          </button>
        ))}
        <span className="text-xs text-muted-foreground ml-auto">{filtered.length} queries</span>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">ID</th>
              <th className="px-3 py-2 text-left text-xs font-medium text-muted-foreground">Query</th>
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-right">Precision</th>
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-right">Recall</th>
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-right">Faith.</th>
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-right">Relev.</th>
              <th className="px-3 py-2 text-xs font-medium text-muted-foreground text-center">Pass</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr
                key={r.id}
                className={cn(
                  "border-b border-border/50 hover:bg-muted/30 transition-colors",
                  i % 2 === 0 ? "" : "bg-muted/20"
                )}
              >
                <td className="px-3 py-2 text-xs font-mono text-muted-foreground whitespace-nowrap">
                  {r.id}
                </td>
                <td className="px-3 py-2 max-w-[240px]">
                  <p className="truncate text-xs" title={r.query}>
                    {r.query}
                  </p>
                  <p className="text-[10px] text-muted-foreground">{r.difficulty}</p>
                </td>
                <ScoreCell score={r.context_precision} />
                <ScoreCell score={r.context_recall} />
                <ScoreCell score={r.answer_faithfulness} />
                <ScoreCell score={r.answer_relevance} />
                <td className="px-3 py-2 text-center">
                  {r.retrieval_pass ? (
                    <span className="text-green-600 dark:text-green-400 text-sm">&#x2713;</span>
                  ) : (
                    <span className="text-red-500 text-sm">&#x2717;</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
