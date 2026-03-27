import { useState, useRef, useEffect } from "react";
import { Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSubmit: (question: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSubmit, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  function handleSubmit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const hasContent = value.trim().length > 0;

  return (
    <div className="w-full border border-input rounded-xl bg-card shadow-sm transition-all duration-200
                    focus-within:ring-2 focus-within:ring-primary/50 focus-within:border-primary/30
                    focus-within:shadow-md">
      <textarea
        ref={textareaRef}
        aria-label="Pertanyaan pajak"
        className="w-full bg-transparent outline-none text-sm text-foreground
                   placeholder:text-muted-foreground disabled:cursor-not-allowed
                   resize-none min-h-[52px] max-h-48 overflow-y-auto px-4 pt-3 pb-1"
        placeholder="Tanya tentang peraturan pajak Indonesia..."
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
      />
      <div className="flex items-center justify-end px-3 pb-3 pt-2 border-t border-border/30">
        <div className="flex items-center gap-2">
          {value.length > 100 && (
            <span className="text-xs text-muted-foreground tabular-nums">{value.length}</span>
          )}
          {!hasContent && !disabled && (
            <span className="text-xs text-muted-foreground hidden sm:inline">Enter untuk kirim</span>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !hasContent}
            aria-label="Kirim pertanyaan"
            className={cn(
              "p-2 rounded-lg transition-colors duration-150 cursor-pointer",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
              "disabled:opacity-40 disabled:cursor-not-allowed",
              hasContent && !disabled
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "text-muted-foreground hover:text-foreground hover:bg-accent"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
