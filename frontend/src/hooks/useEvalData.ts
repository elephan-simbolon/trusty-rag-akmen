import { useState, useEffect, useCallback } from "react";
import { API_BASE_URL } from "@/lib/api";
import type { EvalRun } from "../types/eval";

interface UseEvalDataReturn {
  run: EvalRun | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useEvalData(): UseEvalDataReturn {
  const [run, setRun] = useState<EvalRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchLatest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/api/eval/runs/latest`);
      if (res.status === 404) {
        setRun(null);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: EvalRun = await res.json();
      setRun(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Gagal memuat data evaluasi");
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(() => fetchLatest(), [fetchLatest]);

  useEffect(() => {
    fetchLatest();
  }, [fetchLatest]);

  return { run, loading, error, refresh };
}
