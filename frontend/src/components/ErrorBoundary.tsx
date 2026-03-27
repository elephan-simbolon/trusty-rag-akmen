import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen gap-4 p-8 text-center">
          <h1 className="text-xl font-semibold text-destructive">Terjadi Kesalahan</h1>
          <p className="text-sm text-muted-foreground max-w-md">
            {this.state.error?.message || "Kesalahan tidak diketahui"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90"
          >
            Muat Ulang
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
