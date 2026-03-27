import { useState } from "react";
import { BookOpen, Clipboard, Check } from "lucide-react";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import type { Citation } from "../types/sse";

interface CitationCardProps {
  citation: Citation;
  index: number;
}

export default function CitationCard({ citation, index }: CitationCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(citation.formatted);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* silent */ }
  };

  const pageRef = citation.page_start && citation.page_end && citation.page_start !== citation.page_end
    ? `hal. ${citation.page_start}-${citation.page_end}`
    : citation.page_start
      ? `hal. ${citation.page_start}`
      : null;

  return (
    <div
      id={`citation-${index}`}
      className="flex items-start gap-3 p-3 rounded-lg border border-border/60 bg-card text-sm"
    >
      <div className="flex items-center justify-center w-6 h-6 rounded-md bg-primary/10 shrink-0 mt-0.5">
        <BookOpen className="w-3.5 h-3.5 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-medium leading-snug">[{index + 1}] {citation.book_title}</p>
        <p className="text-muted-foreground text-xs mt-0.5">
          {citation.chapter}{pageRef ? `, ${pageRef}` : ""}
        </p>
        {citation.section_path && (
          <p className="text-muted-foreground/70 text-[11px] mt-0.5 truncate">{citation.section_path}</p>
        )}
      </div>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon-xs" onClick={handleCopy} aria-label="Salin kutipan">
            {copied ? <Check className="h-3 w-3" /> : <Clipboard className="h-3 w-3" />}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top" sideOffset={4}>
          <p className="text-xs">{copied ? "Tersalin!" : "Salin kutipan"}</p>
        </TooltipContent>
      </Tooltip>
    </div>
  );
}
