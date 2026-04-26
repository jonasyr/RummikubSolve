import { create } from "zustand";
import type { SkinId } from "../lib/skins/types";
import { getSkinRenderer } from "../lib/skins/registry";

const PERSIST_KEY = "rummikub_active_skin_v1";

function readPersistedSkinId(): SkinId {
  try {
    const raw = localStorage.getItem(PERSIST_KEY);
    if (raw && typeof raw === "string") return raw;
  } catch {
    // localStorage unavailable (SSR / private browsing)
  }
  return "default";
}

function persistSkinId(id: SkinId): void {
  try {
    localStorage.setItem(PERSIST_KEY, id);
  } catch {
    // ignore write failures (storage quota, private browsing)
  }
}

// Race-condition guard: each setSkin call captures its generation number.
// Only the most recent call may commit its result.
let _callCounter = 0;

interface SkinState {
  activeSkinId: SkinId;
  loadState: "idle" | "loading" | "ready" | "error";
  errorMessage: string | null;
  setSkin(id: SkinId): Promise<void>;
  retryCurrent(): Promise<void>;
  reset(): void;
}

function resolveId(id: SkinId): SkinId {
  return getSkinRenderer(id).manifest.id;
}

export const useSkinStore = create<SkinState>((set, get) => {
  // Hydrate from localStorage; validate against registry (falls back to "default").
  const hydratedId = resolveId(readPersistedSkinId());

  return {
    activeSkinId: hydratedId,
    loadState: "ready",
    errorMessage: null,

    setSkin: async (id: SkinId) => {
      const resolvedId = resolveId(id);

      // No-op: already active and fully loaded.
      if (get().activeSkinId === resolvedId && get().loadState === "ready") return;

      const thisCall = ++_callCounter;
      set({ loadState: "loading", errorMessage: null });

      try {
        await getSkinRenderer(resolvedId).preload();
        if (_callCounter === thisCall) {
          set({ activeSkinId: resolvedId, loadState: "ready" });
          persistSkinId(resolvedId);
        }
      } catch (err) {
        if (_callCounter === thisCall) {
          set({
            loadState: "error",
            errorMessage: err instanceof Error ? err.message : "Failed to load skin",
          });
        }
      }
    },

    retryCurrent: async () => {
      await get().setSkin(get().activeSkinId);
    },

    reset: () => {
      persistSkinId("default");
      set({ activeSkinId: "default", loadState: "ready", errorMessage: null });
    },
  };
});
