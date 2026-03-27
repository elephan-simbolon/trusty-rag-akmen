export type Phase = "idle" | "retrieving" | "generating" | "done" | "error";

export interface Citation {
  book_title: string;
  chapter: string;
  page_start: number;
  page_end: number;
  section_path: string;
  formatted: string;
}

export interface ChatTurn {
  question: string;
  text: string;
  citations: Citation[];
  queryType?: string | null;
  error?: string | null;
}

export interface StreamState {
  phase: Phase;
  statusMessage: string;
  text: string;
  citations: Citation[];
  tokensUsed: number;
  error: string | null;
  historyId: string | null;
  messages: ChatTurn[];
  queryType: string | null;
  cragGrade: string | null;
}

export type SSEEvent =
  | { type: "status"; message: string }
  | { type: "query_type"; query_type: string }
  | { type: "text"; content: string }
  | { type: "citations"; data: Citation[] }
  | { type: "done"; history_id?: string | null; query_type?: string; crag_grade?: string }
  | { type: "not_found"; message: string }
  | { type: "error"; message: string };

export interface HistoryItem {
  id: string;
  question: string;
  answer_preview: string;
  citations_count: number;
  feedback: 1 | -1 | null;
  created_at: string;
}

export interface HistoryDetail extends HistoryItem {
  answer: string;
  citations: Citation[];
  turns?: HistoryTurn[];
}

export interface HistoryTurn {
  question: string;
  answer: string;
  citations: Citation[];
  query_type?: string | null;
}

export interface HistoryListResponse {
  data: HistoryItem[];
  total: number;
  page: number;
  per_page: number;
}
