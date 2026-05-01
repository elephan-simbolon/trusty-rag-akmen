import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { RotateCcw, ChevronDown } from "lucide-react";
import { Button } from "./ui/button";
import CitationCard from "./CitationCard";
import FeedbackButtons from "./FeedbackButtons";
import QueryTypeBadge from "./QueryTypeBadge";
import StatusIndicator from "./StatusIndicator";
import { cn } from "@/lib/utils";
import { CollapsibleRoot, CollapsibleTrigger, CollapsibleContent } from "./ui/collapsible";
import type { Phase, Citation, ChatTurn } from "../types/sse";

function renderWithCitations(
  text: string,
  citations: Citation[],
  openCitationsRef?: React.MutableRefObject<(() => void) | null>,
): React.ReactNode {
  if (!citations.length) return text;
  const parts = text.split(/(\[\d+\]|\[Sumber\s+\d+[^\]]*\]|\[Kerangka\s+\d+[^\]]*\])/g);
  return parts.map((part, i) => {
    const numMatch = part.match(/^\[(?:(?:Sumber|Kerangka)\s+)?(\d+)/);
    if (numMatch) {
      const n = parseInt(numMatch[1]);
      if (n < 1 || n > citations.length) return <span key={i}>{part}</span>;
      return (
        <sup key={i}>
          <a
            href={`#citation-${n - 1}`}
            onClick={(e) => {
              e.preventDefault();
              // auto-open lalu scroll ke target setelah animasi
              openCitationsRef?.current?.();
              setTimeout(() => {
                document.getElementById(`citation-${n - 1}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
              }, 200);
            }}
            className="text-primary hover:text-primary/80 font-semibold no-underline hover:underline transition-colors cursor-pointer px-px"
          >
            [{n}]
          </a>
        </sup>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function renderInlineChildren(
  children: React.ReactNode,
  citations: Citation[],
  openCitationsRef?: React.MutableRefObject<(() => void) | null>,
): React.ReactNode {
  if (!citations.length) return children;
  const arr = Array.isArray(children) ? children : [children];
  return arr.map((child, i) => {
    if (typeof child === "string") {
      return <React.Fragment key={i}>{renderWithCitations(child, citations, openCitationsRef)}</React.Fragment>;
    }
    return child;
  });
}

function MarkdownContent({
  text,
  citations = [],
  openCitationsRef,
}: {
  text: string;
  citations: Citation[];
  openCitationsRef?: React.MutableRefObject<(() => void) | null>;
}) {
  return (
    <div className="text-sm leading-relaxed [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="text-base font-semibold mt-4 mb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-semibold mt-4 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold mt-3 mb-1.5">{children}</h3>,
          p: ({ children }) => (
            <p className="my-1.5">{renderInlineChildren(children, citations, openCitationsRef)}</p>
          ),
          strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="my-1.5 ml-4 list-disc space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="my-1.5 ml-4 list-decimal space-y-0.5">{children}</ol>,
          li: ({ children }) => (
            <li className="leading-relaxed">{renderInlineChildren(children, citations, openCitationsRef)}</li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-primary pl-3 text-muted-foreground italic">
              {children}
            </blockquote>
          ),
          code: ({ children, node }) => {
            const isBlock = node?.position?.start.line !== node?.position?.end.line;
            return isBlock ? (
              <pre className="my-2 rounded-md bg-muted p-3 overflow-x-auto">
                <code className="text-xs font-mono">{children}</code>
              </pre>
            ) : (
              <code className="rounded bg-muted px-1 py-0.5 text-xs font-mono">{children}</code>
            );
          },
          pre: ({ children }) => <>{children}</>,
          hr: () => <hr className="my-3 border-border" />,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="ml-auto self-end bg-secondary rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%]">
      <p className="text-sm">{text}</p>
    </div>
  );
}

function CollapsibleCitationList({
  citations,
  openRef,
}: {
  citations: Citation[];
  openRef?: React.MutableRefObject<(() => void) | null>;
}) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (openRef) {
      openRef.current = () => setOpen(true);
    }
    return () => {
      if (openRef) openRef.current = null;
    };
  }, [openRef]);

  if (!citations.length) return null;

  const seen = new Set<string>();
  const items: { index: number; citation: Citation }[] = [];
  citations.forEach((c, i) => {
    const key = `${c.book_title}|${c.chapter}|${c.page_start}`;
    if (seen.has(key)) return;
    seen.add(key);
    items.push({ index: i, citation: c });
  });

  if (items.length === 0) return null;

  return (
    <div className="mt-1 pt-3 border-t border-border/50">
      <CollapsibleRoot open={open} onOpenChange={setOpen}>
        <CollapsibleTrigger asChild>
          <button className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors cursor-pointer py-1">
            <ChevronDown className={cn("h-3 w-3 transition-transform duration-200", open && "rotate-180")} />
            {open ? "Sembunyikan" : "Lihat"} {items.length} referensi
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="animate-collapsible-down data-[state=closed]:animate-collapsible-up">
          <div className="flex flex-col gap-1.5 mt-2">
            {items.map(({ index, citation }) => (
              <CitationCard key={`${citation.book_title}-${index}`} index={index} citation={citation} />
            ))}
          </div>
        </CollapsibleContent>
      </CollapsibleRoot>
    </div>
  );
}

interface ChatMessageProps {
  phase: Phase;
  statusMessage: string;
  text: string;
  citations: Citation[];
  error: string | null;
  historyId?: string | null;
  currentFeedback?: 1 | -1 | null;
  question?: string;
  messages?: ChatTurn[];
  queryType?: string | null;
  onRetry?: () => void;
}

export default function ChatMessage({
  phase,
  statusMessage,
  text,
  citations,
  error,
  historyId,
  currentFeedback,
  question,
  messages = [],
  queryType,
  onRetry,
}: ChatMessageProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const citationsOpenRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    bottomRef.current?.scrollIntoView({ behavior: prefersReduced ? "instant" : "smooth", block: "end" });
  }, [text, messages.length]);

  if (phase === "idle" && messages.length === 0) return null;

  return (
    <div className="flex flex-col gap-4">
      {messages.map((turn, i) => (
        <div key={i} className="flex flex-col gap-3 pb-4 border-b border-border/50">
          <UserBubble text={turn.question} />
          <div className="flex items-center gap-2">
            <QueryTypeBadge queryType={turn.queryType} />
          </div>
          <MarkdownContent text={turn.text} citations={turn.citations} />
          <CollapsibleCitationList citations={turn.citations || []} />
        </div>
      ))}

      {question && phase !== "idle" && phase !== "done" && (
        <UserBubble text={question} />
      )}

      {phase === "retrieving" && (
        <StatusIndicator message={statusMessage || "Mencari referensi..."} />
      )}

      {phase === "generating" && (
        <div className="relative">
          <MarkdownContent text={text} citations={citations} />
          <span
            className="inline-block w-0.5 h-4 bg-foreground animate-pulse motion-reduce:animate-none ml-0.5 align-text-bottom"
            aria-hidden="true"
          />
        </div>
      )}

      {phase === "done" && (
        <>
          {!text && statusMessage ? (
            <p className="text-sm text-muted-foreground">{statusMessage}</p>
          ) : text ? (
            <>
              <div className="flex items-center gap-2">
                <QueryTypeBadge queryType={queryType} />
              </div>
              <MarkdownContent text={text} citations={citations} openCitationsRef={citationsOpenRef} />
              <CollapsibleCitationList citations={citations} openRef={citationsOpenRef} />
            </>
          ) : null}
          {historyId && (
            <FeedbackButtons
              historyId={historyId}
              currentFeedback={currentFeedback || null}
              answerText={text || messages[messages.length - 1]?.text || ""}
              onRetry={onRetry}
            />
          )}
        </>
      )}

      {phase === "error" && (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
          <p className="text-sm text-destructive font-medium">Terjadi kesalahan</p>
          <p className="text-sm text-destructive/80 mt-1">{error}</p>
          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-muted-foreground">Coba ajukan pertanyaan kembali.</p>
            {onRetry && (
              <Button variant="ghost" size="icon" onClick={onRetry} aria-label="Coba lagi"
                className="text-muted-foreground hover:text-foreground">
                <RotateCcw className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
