import { useState, useCallback, useEffect } from "react";
import type { HistoryItem, HistoryDetail } from "../types/sse";
import { GripVertical, Menu, SquarePen, Settings } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";
import { HistoryItemActions } from "./HistoryItemActions";
import {
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  useSidebar,
} from "./ui/sidebar";
import { SidebarNavButton } from "./ui/sidebar-nav-button";

interface HistorySidebarProps {
  userId: string | null;
  onRestore: (detail: HistoryDetail) => void;
  activeId: string | null;
  items: HistoryItem[];
  loading: boolean;
  onDelete: (id: string) => void;
  onRename: (id: string, newTitle: string) => void;
  onNewChat: () => void;
}

const MIN_SIDEBAR_WIDTH = 200;
const MAX_SIDEBAR_WIDTH = 400;
const SIDEBAR_WIDTH_STORAGE_KEY = "sidebar:width";

function groupByDate(items: HistoryItem[]): Map<string, HistoryItem[]> {
  const groups = new Map<string, HistoryItem[]>();
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  for (const item of items) {
    const date = new Date(item.created_at);
    let label: string;
    if (date >= today) label = "Hari ini";
    else if (date >= yesterday) label = "Kemarin";
    else if (date >= weekAgo) label = "7 hari terakhir";
    else label = "Lebih lama";

    if (!groups.has(label)) groups.set(label, []);
    groups.get(label)!.push(item);
  }
  return groups;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Baru saja";
  if (diffMins < 60) return `${diffMins} menit lalu`;
  if (diffHours < 24) return `${diffHours} jam lalu`;
  if (diffDays < 7) return `${diffDays} hari lalu`;
  return date.toLocaleDateString("id-ID");
}

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

export function HistorySidebar({ userId, onRestore, activeId, items, loading, onDelete, onRename, onNewChat }: HistorySidebarProps) {
  const { open, toggleSidebar } = useSidebar();
  const [isResizing, setIsResizing] = useState(false);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem(SIDEBAR_WIDTH_STORAGE_KEY);
      if (saved) {
        const parsed = parseInt(saved, 10);
        if (!isNaN(parsed) && parsed >= MIN_SIDEBAR_WIDTH && parsed <= MAX_SIDEBAR_WIDTH) {
          return parsed;
        }
      }
    }
    return 280;
  });

  useEffect(() => {
    localStorage.setItem(SIDEBAR_WIDTH_STORAGE_KEY, sidebarWidth.toString());
  }, [sidebarWidth]);

  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResize = useCallback(() => setIsResizing(false), []);

  const resize = useCallback((e: MouseEvent) => {
    if (!isResizing) return;
    setSidebarWidth(Math.min(Math.max(e.clientX, MIN_SIDEBAR_WIDTH), MAX_SIDEBAR_WIDTH));
  }, [isResizing]);

  useEffect(() => {
    if (!isResizing) return;
    window.addEventListener("mousemove", resize);
    window.addEventListener("mouseup", stopResize);
    return () => {
      window.removeEventListener("mousemove", resize);
      window.removeEventListener("mouseup", stopResize);
    };
  }, [isResizing, resize, stopResize]);

  const groups = groupByDate(items);
  const isEmpty = items.length === 0 && !loading;

  return (
    <>
      <div
        className="h-full flex flex-col bg-sidebar text-sidebar-foreground border-r border-sidebar-border overflow-hidden shrink-0"
        style={{
          width: open ? sidebarWidth : 48,
          minWidth: open ? sidebarWidth : 48,
          maxWidth: open ? sidebarWidth : 48,
          transition: isResizing ? "none" : "width 0.2s ease-out",
        }}
      >
        {/* Header: toggle + new chat */}
        <div className="flex flex-col gap-1 px-1 py-2 shrink-0">
          <SidebarNavButton
            icon={Menu}
            label={open ? "Ciutkan menu" : "Perluas menu"}
            expanded={open}
            showLabelWhenExpanded={false}
            onClick={toggleSidebar}
          />
          <SidebarNavButton
            icon={SquarePen}
            label="Chat baru"
            expanded={open}
            onClick={onNewChat}
          />
        </div>

        {/* Content: riwayat — hanya saat expanded */}
        {open && (
          <SidebarContent>
            {loading && items.length === 0 ? (
              <SidebarGroup>
                <SidebarGroupContent>
                  <SidebarMenu>
                    {[...Array(3)].map((_, i) => (
                      <SidebarMenuItem key={i}>
                        <SidebarMenuSkeleton showIcon={false} />
                      </SidebarMenuItem>
                    ))}
                  </SidebarMenu>
                </SidebarGroupContent>
              </SidebarGroup>
            ) : isEmpty ? (
              <SidebarGroup>
                <SidebarGroupContent>
                  <p className="text-sm text-muted-foreground px-2 py-4 text-center">
                    Belum ada riwayat pertanyaan
                  </p>
                </SidebarGroupContent>
              </SidebarGroup>
            ) : (
              Array.from(groups.entries()).map(([label, groupItems]) => (
                <SidebarGroup key={label}>
                  <SidebarGroupLabel>{label}</SidebarGroupLabel>
                  <SidebarGroupContent>
                    <SidebarMenu>
                      {groupItems.map((item) => (
                        <SidebarMenuItem key={item.id} className="group/item relative">
                          <SidebarMenuButton
                            asChild
                            isActive={activeId === item.id}
                            onClick={() => {
                              if (renamingId === item.id) return;
                              fetch(`${API_BASE_URL}/api/history/${item.id}?user_id=${userId}`)
                                .then((res) => res.json())
                                .then((detail: HistoryDetail) => onRestore(detail))
                                .catch((err) => console.error("Failed to restore history:", err));
                            }}
                          >
                            <button className="w-full text-left pr-6">
                              <div className="flex flex-col gap-0.5 min-w-0">
                                {renamingId === item.id ? (
                                  <HistoryItemActions
                                    currentTitle={item.question}
                                    isRenaming={true}
                                    onStartRename={() => setRenamingId(item.id)}
                                    onConfirmRename={(t) => { onRename(item.id, t); setRenamingId(null); }}
                                    onCancelRename={() => setRenamingId(null)}
                                    onDelete={() => onDelete(item.id)}
                                  />
                                ) : (
                                  <>
                                    <span className="truncate text-sm">{truncateText(item.question, 50)}</span>
                                    <span className="text-xs text-muted-foreground">
                                      {formatRelativeTime(item.created_at)}
                                    </span>
                                  </>
                                )}
                              </div>
                            </button>
                          </SidebarMenuButton>
                          {renamingId !== item.id && (
                            <HistoryItemActions
                              currentTitle={item.question}
                              isRenaming={false}
                              onStartRename={() => setRenamingId(item.id)}
                              onConfirmRename={(t) => { onRename(item.id, t); setRenamingId(null); }}
                              onCancelRename={() => setRenamingId(null)}
                              onDelete={() => onDelete(item.id)}
                            />
                          )}
                        </SidebarMenuItem>
                      ))}
                    </SidebarMenu>
                  </SidebarGroupContent>
                </SidebarGroup>
              ))
            )}
          </SidebarContent>
        )}

        {/* Footer: settings */}
        <div className="mt-auto px-1 py-2 shrink-0">
          <SidebarNavButton
            icon={Settings}
            label="Pengaturan"
            expanded={open}
          />
        </div>
      </div>

      {open && (
        <div
          className="w-1 cursor-col-resize bg-border hover:bg-primary/30 transition-colors flex items-center justify-center group"
          onMouseDown={startResize}
          role="separator"
          aria-label="Ubah lebar sidebar"
        >
          <GripVertical className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      )}
    </>
  );
}
