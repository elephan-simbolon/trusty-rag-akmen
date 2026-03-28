import { useState, useCallback, useRef } from "react";
import type { StreamState, SSEEvent, HistoryDetail, ChatTurn } from "../types/sse";
import { API_BASE_URL } from "@/lib/api";

const INITIAL_STATE: StreamState = {
  phase: "idle",
  statusMessage: "",
  text: "",
  citations: [],
  tokensUsed: 0,
  error: null,
  historyId: null,
  messages: [],
  queryType: null,
  cragGrade: null,
};

export function useStreamingQuery() {
  const [state, setState] = useState<StreamState>(INITIAL_STATE);
  const abortRef = useRef<AbortController | null>(null);
  const currentQuestionRef = useRef<string>("");
  const sessionIdRef = useRef<string>(crypto.randomUUID());

  const submit = useCallback(async (question: string) => {
    abortRef.current?.abort();
    const abort = new AbortController();
    abortRef.current = abort;
    currentQuestionRef.current = question;

    setState(prev => ({ ...INITIAL_STATE, phase: "retrieving", messages: prev.messages }));

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/query`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            session_id: sessionIdRef.current,
          }),
          signal: abort.signal,
        }
      );

      if (!response.ok) {
        setState(prev => ({ ...prev, phase: "error", error: `Server error: ${response.status}` }));
        return;
      }

      if (!response.body) return;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split(/\r\n\r\n|\n\n/);
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const dataLine = part.split(/\r\n|\n/).find(l => l.startsWith("data: "));
          if (!dataLine) continue;
          let event: SSEEvent;
          try {
            event = JSON.parse(dataLine.slice(6)) as SSEEvent;
          } catch {
            continue;
          }

          switch (event.type) {
            case "status":
              setState(prev => ({ ...prev, statusMessage: event.message }));
              break;
            case "query_type":
              setState(prev => ({ ...prev, queryType: event.query_type }));
              break;
            case "text":
              setState(prev => ({
                ...prev,
                phase: "generating",
                statusMessage: "",
                text: prev.text + event.content,
              }));
              break;
            case "citations":
              setState(prev => ({ ...prev, citations: event.data }));
              break;
            case "done": {
              const completedQuestion = currentQuestionRef.current;
              const newHistoryId = event.history_id || null;
              setState(prev => {
                const newTurn: ChatTurn = {
                  question: completedQuestion,
                  text: prev.text,
                  citations: prev.citations,
                  queryType: prev.queryType,
                };
                return {
                  ...prev,
                  phase: "done",
                  statusMessage: "",
                  historyId: newHistoryId,
                  cragGrade: event.crag_grade || null,
                  text: "",
                  citations: [],
                  queryType: null,
                  messages: [...prev.messages, newTurn],
                };
              });
              break;
            }
            case "not_found": {
              const completedQuestion = currentQuestionRef.current;
              setState(prev => {
                const newTurn: ChatTurn = {
                  question: completedQuestion,
                  text: event.message,
                  citations: [],
                };
                return {
                  ...prev,
                  phase: "done",
                  statusMessage: "",
                  text: "",
                  citations: [],
                  queryType: null,
                  messages: [...prev.messages, newTurn],
                };
              });
              break;
            }
            case "error":
              setState(prev => ({ ...prev, phase: "error", error: event.message }));
              break;
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setState(prev => ({
        ...prev,
        phase: "error",
        error: "Gagal menghubungi server. Periksa koneksi dan coba lagi.",
      }));
    }
  }, []);

  const restoreFromHistory = useCallback((detail: HistoryDetail) => {
    abortRef.current?.abort();
    const restoredMessages: ChatTurn[] = detail.turns && detail.turns.length > 0
      ? detail.turns.map(t => ({
          question: t.question,
          text: t.answer,
          citations: t.citations || [],
          queryType: t.query_type || null,
        }))
      : [{ question: detail.question, text: detail.answer, citations: detail.citations || [] }];

    setState({
      ...INITIAL_STATE,
      phase: "done",
      historyId: detail.id,
      messages: restoredMessages,
    });
  }, []);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    setState(INITIAL_STATE);
  }, []);

  return { ...state, submit, restoreFromHistory, clear };
}
