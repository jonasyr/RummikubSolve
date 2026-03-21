"use client";

import { Component, type ReactNode } from "react";
import { useTranslations } from "next-intl";

interface Props {
  children: ReactNode;
  heading?: string;
  fallback?: string;
}

interface State {
  hasError: boolean;
  message: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: unknown): State {
    return {
      hasError: true,
      message: error instanceof Error ? error.message : "Unknown rendering error",
    };
  }

  override render() {
    if (this.state.hasError) {
      const heading = this.props.heading ?? "Something went wrong displaying the result.";
      const fallback = this.props.fallback ?? this.state.message;
      return (
        <div
          role="alert"
          className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm space-y-1"
        >
          <p className="font-semibold">{heading}</p>
          <p className="text-xs text-red-500">{fallback}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

// Functional wrapper that injects translated strings into ErrorBoundary.
export function TranslatedErrorBoundary({ children }: { children: ReactNode }) {
  const t = useTranslations("errorBoundary");
  return (
    <ErrorBoundary heading={t("heading")} fallback={t("fallback")}>
      {children}
    </ErrorBoundary>
  );
}
