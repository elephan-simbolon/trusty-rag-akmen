import type { LucideIcon } from "lucide-react";
import { Button } from "./button";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";
import { cn } from "@/lib/utils";

interface SidebarNavButtonProps {
  icon: LucideIcon;
  label: string;
  expanded: boolean;
  showLabelWhenExpanded?: boolean;
  onClick?: () => void;
  className?: string;
}

export function SidebarNavButton({
  icon: Icon,
  label,
  expanded,
  showLabelWhenExpanded = true,
  onClick,
  className,
}: SidebarNavButtonProps) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={onClick}
          aria-label={label}
          className={cn(
            "w-full justify-start gap-3 px-2 text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            className
          )}
        >
          <Icon className="w-4 h-4 shrink-0" />
          {expanded && showLabelWhenExpanded && (
            <span className="text-sm font-medium truncate">{label}</span>
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}
