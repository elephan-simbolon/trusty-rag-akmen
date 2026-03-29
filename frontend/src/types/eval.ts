// Types untuk RAGAS evaluation dashboard

export interface EvalMetricScores {
  context_precision: number | null;
  context_recall: number | null;
  answer_faithfulness: number | null;
  answer_relevance: number | null;
}

export interface EvalSummary extends EvalMetricScores {
  retrieval_accuracy: number | null;
  total_queries: number;
  per_difficulty?: Record<string, EvalMetricScores>;
}

export interface EvalQueryResult extends EvalMetricScores {
  id: string;
  query: string;
  difficulty: "Simple" | "Medium" | "Complex" | "Calculation";
  retrieval_pass: boolean;
  crag_grade?: string | null;
  query_type?: string | null;
}

export interface EvalRun {
  id: string;
  run_at: string;
  model: string;
  query_count: number;
  summary: EvalSummary;
  results: EvalQueryResult[];
}

export interface EvalRunsListResponse {
  data: Omit<EvalRun, "results">[];
  total: number;
}
