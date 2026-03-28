import { useState, useEffect } from "react";
import { Sun, Moon } from "lucide-react";
import { Toaster } from "sonner";
import { TooltipProvider } from "./components/ui/tooltip";
import { SidebarProvider, SidebarInset } from "./components/ui/sidebar";
import { Button } from "./components/ui/button";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { useStreamingQuery } from "./hooks/useStreamingQuery";
import { useHistory } from "./hooks/useHistory";
import { useHistoryActions } from "./hooks/useHistoryActions";
import ChatInput from "./components/ChatInput";
import ChatMessage from "./components/ChatMessage";
import EmptyState from "./components/EmptyState";
import BrandLogo from "./components/BrandLogo";
import { HistorySidebar } from "./components/HistorySidebar";
import type { HistoryDetail } from "./types/sse";

function App() {
  const [currentFeedback, setCurrentFeedback] = useState<1 | -1 | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>("");
  const [isDark, setIsDark] = useState<boolean>(() => localStorage.getItem("theme") !== "light");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
  }, [isDark]);

  const {
    phase,
    statusMessage,
    text,
    citations,
    error,
    historyId,
    messages,
    queryType,
    submit,
    restoreFromHistory,
    clear,
  } = useStreamingQuery();

  const { items, loading: historyLoading, refresh: refreshHistory, setItems } = useHistory();
  const isLoading = phase === "retrieving" || phase === "generating";

  useEffect(() => {
    if (phase === "done" && historyId) refreshHistory();
  }, [phase, historyId, refreshHistory]);

  const handleRestore = (detail: HistoryDetail) => {
    restoreFromHistory(detail);
    setCurrentFeedback(detail.feedback ?? null);
    setLastQuestion(detail.question);
  };

  const handleNewChat = () => {
    clear();
    setCurrentFeedback(null);
  };

  const { deleteItem, renameItem } = useHistoryActions({
    items,
    setItems,
    activeId: historyId,
    onDeleteActive: handleNewChat,
  });

  const handleSubmit = (question: string) => {
    if (!historyId) clear();
    setCurrentFeedback(null);
    setLastQuestion(question);
    submit(question);
  };

  const handleRetry = () => {
    if (!lastQuestion || isLoading) return;
    submit(lastQuestion);
  };

  return (
    <ErrorBoundary>
      <TooltipProvider>
        <SidebarProvider>
          <div className="flex h-screen w-full bg-background">
            <HistorySidebar
              userId={null}
              onRestore={handleRestore}
              activeId={historyId}
              items={items}
              loading={historyLoading}
              onDelete={deleteItem}
              onRename={renameItem}
              onNewChat={handleNewChat}
            />
            <SidebarInset className="flex flex-col min-w-0">
              <header className="flex items-center justify-between gap-3 px-4 py-3 border-b border-border/50 shrink-0
                                 bg-background/95 backdrop-blur-sm sticky top-0 z-10">
                <div className="flex items-center">
                  <BrandLogo />
                </div>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setIsDark(d => !d)}
                  aria-label={isDark ? "Aktifkan mode terang" : "Aktifkan mode gelap"}
                >
                  {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                </Button>
              </header>

              <main className="flex-1 overflow-y-auto">
                <div className="max-w-3xl mx-auto px-6 py-6">
                  {phase === "idle" && messages.length === 0 ? (
                    <EmptyState onSuggestionClick={handleSubmit} />
                  ) : (
                    <ChatMessage
                      phase={phase}
                      statusMessage={statusMessage}
                      text={text}
                      citations={citations}
                      error={error}
                      historyId={historyId}
                      currentFeedback={currentFeedback}
                      question={lastQuestion}
                      messages={messages}
                      queryType={queryType}
                      onRetry={lastQuestion && !isLoading ? handleRetry : undefined}
                    />
                  )}
                </div>
              </main>

              <footer className="shrink-0 border-t border-border/50 bg-background/95 backdrop-blur-sm">
                <div className="max-w-3xl mx-auto px-6 py-4">
                  <ChatInput onSubmit={handleSubmit} disabled={isLoading} />
                </div>
              </footer>
            </SidebarInset>
          </div>
        </SidebarProvider>
        <Toaster />
      </TooltipProvider>
    </ErrorBoundary>
  );
}

export default App;
