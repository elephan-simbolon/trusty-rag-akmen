import { BookOpen } from "lucide-react";

export default function BrandLogo() {
  return (
    <div className="flex items-center gap-2.5">
      <div className="flex items-center justify-center w-8 h-8 rounded-full bg-primary/10">
        <BookOpen className="w-4 h-4 text-primary" />
      </div>
      <div className="flex flex-col">
        <span className="text-sm font-bold leading-tight tracking-tight">Trusty RAG Akmen</span>
        <span className="text-[10px] text-muted-foreground leading-tight">Asisten Akuntansi Biaya &amp; Manajemen</span>
      </div>
    </div>
  );
}
