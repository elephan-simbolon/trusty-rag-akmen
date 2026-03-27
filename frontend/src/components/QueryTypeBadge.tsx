import { Badge } from "./ui/badge";

const BADGE_CONFIG: Record<string, { label: string; className: string }> = {
  Calculation: { label: "Kalkulasi", className: "bg-orange-500/15 text-orange-700 dark:text-orange-300 border-orange-500/25" },
  Medium: { label: "Analisis", className: "bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/25" },
  Complex: { label: "Mendalam", className: "bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/25" },
};

export default function QueryTypeBadge({ queryType }: { queryType: string | null | undefined }) {
  if (!queryType || queryType === "Simple") return null;
  const config = BADGE_CONFIG[queryType];
  if (!config) return null;

  return (
    <Badge variant="outline" className={`text-[10px] font-medium ${config.className}`}>
      {config.label}
    </Badge>
  );
}
