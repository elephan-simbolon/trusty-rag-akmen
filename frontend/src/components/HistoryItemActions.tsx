import { useState, useRef, useEffect } from "react";
import { MoreHorizontal, Pencil, Trash2 } from "lucide-react";
import { Button } from "./ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "./ui/dropdown-menu";

interface HistoryItemActionsProps {
  currentTitle: string;
  isRenaming: boolean;
  onStartRename: () => void;
  onConfirmRename: (newTitle: string) => void;
  onCancelRename: () => void;
  onDelete: () => void;
}

export function HistoryItemActions({
  currentTitle,
  isRenaming,
  onStartRename,
  onConfirmRename,
  onCancelRename,
  onDelete,
}: HistoryItemActionsProps) {
  const [draftTitle, setDraftTitle] = useState(currentTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming) {
      setDraftTitle(currentTitle);
      requestAnimationFrame(() => {
        inputRef.current?.focus();
        inputRef.current?.select();
      });
    }
  }, [isRenaming, currentTitle]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onConfirmRename(draftTitle);
    } else if (e.key === "Escape") {
      e.preventDefault();
      onCancelRename();
    }
  };

  if (isRenaming) {
    return (
      <input
        ref={inputRef}
        value={draftTitle}
        onChange={e => setDraftTitle(e.target.value)}
        onBlur={() => onConfirmRename(draftTitle)}
        onKeyDown={handleKeyDown}
        className="w-full bg-transparent text-sm text-foreground border-b border-primary outline-none py-0.5 px-0"
        aria-label="Ubah nama riwayat"
      />
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon-xs"
          className="opacity-0 group-hover/item:opacity-100 focus-visible:opacity-100 shrink-0 absolute right-1 top-1/2 -translate-y-1/2"
          aria-label="Opsi riwayat"
          onClick={e => e.stopPropagation()}
        >
          <MoreHorizontal />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" side="bottom">
        <DropdownMenuItem onSelect={onStartRename}>
          <Pencil />
          Ganti Nama
        </DropdownMenuItem>
        <DropdownMenuItem data-variant="destructive" onSelect={onDelete}>
          <Trash2 />
          Hapus
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
