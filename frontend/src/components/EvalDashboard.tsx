import { BarChart3, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";
import { MetricCard } from "./eval/MetricCard";
import { RadarChart } from "./eval/RadarChart";
import { DifficultyChart } from "./eval/DifficultyChart";
import { QueryResultTable } from "./eval/QueryResultTable";
import { useEvalData } from "../hooks/useEvalData";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("id-ID", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function EvalDashboard() {
  const { run, loading, error, refresh } = useEvalData();

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-5xl mx-auto px-6 py-6 flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-foreground">Evaluasi Kualitas RAG</h1>
            <p className="text-sm text-muted-foreground">
              {run
                ? `Run terakhir: ${formatDate(run.run_at)} — ${run.query_count} queries`
                : "Belum ada data evaluasi"}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {/* Error state */}
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && !run && (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
            <BarChart3 className="w-10 h-10 text-muted-foreground/40" />
            <p className="text-sm font-medium text-muted-foreground">Belum ada data evaluasi</p>
            <p className="text-xs text-muted-foreground/70 max-w-xs">
              Jalankan evaluasi dari CLI terlebih dahulu:
            </p>
            <code className="text-xs bg-muted px-3 py-1.5 rounded font-mono">
              uv run python scripts/evaluate_retrieval.py --ragas
            </code>
          </div>
        )}

        {/* Data tersedia */}
        {run && (
          <>
            {/* 4 Metric Cards */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MetricCard
                label="Context Precision"
                score={run.summary.context_precision}
                description="Proporsi chunk relevan yang di-retrieve"
              />
              <MetricCard
                label="Context Recall"
                score={run.summary.context_recall}
                description="Coverage klaim golden answer oleh context"
              />
              <MetricCard
                label="Answer Faithfulness"
                score={run.summary.answer_faithfulness}
                description="Proporsi klaim jawaban yang bisa diverifikasi"
              />
              <MetricCard
                label="Answer Relevance"
                score={run.summary.answer_relevance}
                description="Seberapa relevan jawaban dengan pertanyaan"
              />
            </div>

            {/* Radar + Retrieval accuracy */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="sm:col-span-1 flex flex-col items-center justify-center rounded-lg border border-border bg-card p-4">
                <RadarChart scores={run.summary} />
              </div>
              <div className="sm:col-span-2 rounded-lg border border-border bg-card p-4 flex flex-col gap-2 justify-center">
                <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
                  Retrieval Accuracy (Citation)
                </p>
                <p className="text-3xl font-bold tabular-nums text-foreground">
                  {run.summary.retrieval_accuracy !== null
                    ? `${Math.round(run.summary.retrieval_accuracy * 100)}%`
                    : "—"}
                </p>
                <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${(run.summary.retrieval_accuracy ?? 0) * 100}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Target &ge;85% (17/20 queries dengan citation buku yang benar)
                </p>
              </div>
            </div>

            {/* Per-difficulty chart */}
            {run.summary.per_difficulty && (
              <div className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-foreground">Score per Difficulty</h2>
                <DifficultyChart perDifficulty={run.summary.per_difficulty} />
              </div>
            )}

            {/* Query result table */}
            <div className="flex flex-col gap-3">
              <h2 className="text-sm font-semibold text-foreground">Detail per Query</h2>
              <QueryResultTable results={run.results} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
