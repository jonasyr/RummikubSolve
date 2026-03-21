"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
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
      return (
        <div
          role="alert"
          className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm space-y-1"
        >
          <p className="font-semibold">Something went wrong displaying the result.</p>
          <p className="text-xs text-red-500">{this.state.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
