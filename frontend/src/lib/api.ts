import type { PuzzleRequest, PuzzleResponse, SolveRequest, SolveResponse } from "../types/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function solvePuzzle(
  request: SolveRequest,
  signal?: AbortSignal,
): Promise<SolveResponse> {
  const res = await fetch(`${API_URL}/api/solve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as {
      detail?: string | Array<{ msg: string }>;
    };
    let message: string;
    if (Array.isArray(data.detail)) {
      message = data.detail.map((e) => e.msg).join("; ");
    } else {
      message = data.detail ?? `HTTP ${res.status}`;
    }
    throw new Error(message);
  }

  return res.json() as Promise<SolveResponse>;
}

export async function fetchPuzzle(
  request: PuzzleRequest = {},
  signal?: AbortSignal,
): Promise<PuzzleResponse> {
  const res = await fetch(`${API_URL}/api/puzzle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    const data = (await res.json().catch(() => ({}))) as {
      detail?: string | Array<{ msg: string }>;
    };
    let message: string;
    if (Array.isArray(data.detail)) {
      message = data.detail.map((e) => e.msg).join("; ");
    } else {
      message = data.detail ?? `HTTP ${res.status}`;
    }
    throw new Error(message);
  }

  return res.json() as Promise<PuzzleResponse>;
}
