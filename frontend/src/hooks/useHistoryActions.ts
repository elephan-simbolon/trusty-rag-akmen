import { useCallback } from "react";
import { toast } from "sonner";
import type { HistoryItem } from "../types/sse";

interface UseHistoryActionsProps {
  items: HistoryItem[];
  setItems: React.Dispatch<React.SetStateAction<HistoryItem[]>>;
  activeId: string | null;
  onDeleteActive?: () => void;
}

interface UseHistoryActionsReturn {
  deleteItem: (id: string) => Promise<void>;
  renameItem: (id: string, newTitle: string) => Promise<void>;
}

export function useHistoryActions({
  items,
  setItems,
  activeId,
  onDeleteActive,
}: UseHistoryActionsProps): UseHistoryActionsReturn {

  const deleteItem = useCallback(async (id: string) => {
    const snapshot = items;
    setItems(prev => prev.filter(item => item.id !== id));
    if (id === activeId) onDeleteActive?.();

    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/history/${id}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error("Gagal menghapus riwayat");
      toast.success("Riwayat dihapus");
    } catch (e) {
      setItems(snapshot);
      toast.error(e instanceof Error ? e.message : "Gagal menghapus riwayat");
    }
  }, [items, setItems, activeId, onDeleteActive]);

  const renameItem = useCallback(async (id: string, newTitle: string) => {
    const trimmed = newTitle.trim();
    if (!trimmed) return;

    const snapshot = items;
    setItems(prev =>
      prev.map(item => item.id === id ? { ...item, question: trimmed } : item)
    );

    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_BASE_URL}/api/history/${id}/title`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: trimmed }),
        }
      );
      if (!res.ok) throw new Error("Gagal mengubah nama riwayat");
      toast.success("Nama riwayat diperbarui");
    } catch (e) {
      setItems(snapshot);
      toast.error(e instanceof Error ? e.message : "Gagal mengubah nama riwayat");
    }
  }, [items, setItems]);

  return { deleteItem, renameItem };
}
