import { BookOpen, Calculator, BarChart3, TrendingUp } from "lucide-react";

const SUGGESTIONS = [
  { icon: TrendingUp, text: "Apa itu break-even point?" },
  { icon: BarChart3, text: "Jelaskan metode Activity-Based Costing" },
  { icon: Calculator, text: "Bagaimana cara menghitung HPP?" },
  { icon: BookOpen, text: "Apa perbedaan biaya tetap dan variabel?" },
];

interface EmptyStateProps {
  onSuggestionClick: (question: string) => void;
}

export default function EmptyState({ onSuggestionClick }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8 px-4">
      <div className="flex flex-col items-center gap-3 text-center">
        <div className="flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10">
          <BookOpen className="w-7 h-7 text-primary" />
        </div>
        <h2 className="text-xl font-semibold">Apa yang ingin Anda pelajari?</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          Tanyakan konsep akuntansi biaya dan manajemen — jawaban disertai kutipan sumber textbook.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
        {SUGGESTIONS.map(({ icon: Icon, text }) => (
          <button
            key={text}
            onClick={() => onSuggestionClick(text)}
            className="flex items-center gap-3 px-4 py-3 text-left text-sm rounded-xl
                       border border-border/60 bg-card hover:bg-accent/50
                       transition-colors cursor-pointer"
          >
            <Icon className="w-4 h-4 text-muted-foreground shrink-0" />
            <span>{text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
