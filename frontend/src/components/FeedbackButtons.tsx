import { useState } from "react";
import { ThumbsUp, ThumbsDown, RotateCcw, Clipboard, Check } from "lucide-react";
import { Button } from "./ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./ui/tooltip";
import { toast } from "sonner";

interface FeedbackButtonsProps {
  historyId: string;
  currentFeedback: 1 | -1 | null;
  answerText: string;
  onRetry?: () => void;
}

export default function FeedbackButtons({ historyId, currentFeedback, answerText, onRetry }: FeedbackButtonsProps) {
  const [feedback, setFeedback] = useState<1 | -1 | null>(currentFeedback);
  const [isLoading, setIsLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(answerText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Gagal menyalin jawaban");
    }
  };

  const handleClick = async (value: 1 | -1) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/api/history/${historyId}/feedback`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: value }),
      });
      if (!res.ok) throw new Error("Failed to save feedback");
      setFeedback(value);
    } catch {
      toast.error("Gagal menyimpan feedback");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex gap-1 mt-2">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button variant="ghost" size="icon" onClick={handleCopy} aria-label="Salin jawaban">
            {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
          </Button>
        </TooltipTrigger>
        <TooltipContent side="top" sideOffset={4}>
          <p className="text-xs">{copied ? "Tersalin!" : "Salin jawaban"}</p>
        </TooltipContent>
      </Tooltip>
      <div className="w-px h-4 bg-border mx-0.5 self-center" aria-hidden="true" />
      <Button
        variant={feedback === 1 ? "default" : "ghost"}
        size="icon"
        onClick={() => handleClick(1)}
        disabled={feedback !== null || isLoading}
        aria-label="Jawaban berguna"
        className={feedback === 1 ? "bg-primary hover:bg-primary/90" : ""}
      >
        <ThumbsUp className="h-4 w-4" />
      </Button>
      <Button
        variant={feedback === -1 ? "destructive" : "ghost"}
        size="icon"
        onClick={() => handleClick(-1)}
        disabled={feedback !== null || isLoading}
        aria-label="Jawaban kurang tepat"
      >
        <ThumbsDown className="h-4 w-4" />
      </Button>
      {onRetry && (
        <>
          <div className="w-px h-4 bg-border mx-0.5 self-center" aria-hidden="true" />
          <Button variant="ghost" size="icon" onClick={onRetry} aria-label="Coba lagi">
            <RotateCcw className="h-4 w-4" />
          </Button>
        </>
      )}
    </div>
  );
}
