import { useState, useEffect, useCallback } from "react";
import type { HistoryItem, HistoryListResponse } from "../types/sse";

interface UseHistoryReturn {
  items: HistoryItem[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  setItems: React.Dispatch<React.SetStateAction<HistoryItem[]>>;
}

export function useHistory(): UseHistoryReturn {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/history?page=1&per_page=20`
      );
      if (!res.ok) throw new Error("Failed to fetch history");
      const data: HistoryListResponse = await res.json();
      setItems(data.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(() => fetchHistory(), [fetchHistory]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return { items, loading, error, refresh, setItems };
}
