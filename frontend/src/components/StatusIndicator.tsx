interface StatusIndicatorProps {
  message?: string;
}

export default function StatusIndicator({ message }: StatusIndicatorProps) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-2 text-sm text-muted-foreground py-1">
      <span aria-hidden="true" className="flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-primary motion-reduce:opacity-60
                         [animation:dot-pulse_1.4s_ease-in-out_infinite]" />
        <span className="w-1.5 h-1.5 rounded-full bg-primary motion-reduce:opacity-60
                         [animation:dot-pulse_1.4s_ease-in-out_0.2s_infinite]" />
        <span className="w-1.5 h-1.5 rounded-full bg-primary motion-reduce:opacity-60
                         [animation:dot-pulse_1.4s_ease-in-out_0.4s_infinite]" />
      </span>
      <span>{message || "Memproses..."}</span>
    </div>
  );
}
