import { Component, type ReactNode } from "react";

export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-xl p-8">
          <h1 className="text-lg font-semibold">Something went wrong</h1>
          <p className="mt-2 text-sm text-muted">{this.state.error.message}</p>
          <button className="mt-4 text-sm text-accent" onClick={() => this.setState({ error: null })}>
            Continue
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
