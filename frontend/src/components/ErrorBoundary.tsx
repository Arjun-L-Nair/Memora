import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * ErrorBoundary
 *
 * Without this, an uncaught render-time error anywhere in the app
 * unmounts the entire React tree and leaves a blank white page with
 * nothing but a console error — genuinely hard to diagnose remotely
 * (a blank page could be almost anything: a network failure, a CSS
 * issue, a JS crash, a build problem). This catches render errors and
 * shows the actual error message on-screen instead, so whoever hits
 * it can immediately see and report what actually broke rather than
 * just "the page is blank."
 *
 * Deliberately a class component — React's error boundary API
 * (getDerivedStateFromError / componentDidCatch) has no hook
 * equivalent as of this writing; this is the correct, standard
 * pattern, not a stylistic choice.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error("Memora crashed:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
          <h1 className="font-display text-2xl font-semibold text-foreground">Something went wrong</h1>
          <p className="max-w-md text-sm text-muted-foreground">
            This page hit an unexpected error. Reloading usually fixes it — if it keeps
            happening, the message below is what to report.
          </p>
          <pre className="max-w-lg overflow-auto rounded-md border border-border bg-muted p-3 text-left text-xs text-error-600">
            {this.state.error.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            className="rounded-xl bg-primary px-5 py-2.5 text-sm shadow-soft font-medium text-primary-foreground"
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
