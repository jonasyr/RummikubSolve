"use client";

import React, { createContext, useContext } from "react";
import type { SkinRenderer } from "./types";
import { defaultSkinRenderer } from "./default-skin";

const SkinContext = createContext<SkinRenderer>(defaultSkinRenderer);

export function SkinProvider({ children }: { children: React.ReactNode }) {
  // Phase 1: always the default renderer. Phase 2 will read from the Zustand store.
  return (
    <SkinContext.Provider value={defaultSkinRenderer}>
      {children}
    </SkinContext.Provider>
  );
}

export function useActiveSkinRenderer(): SkinRenderer {
  return useContext(SkinContext);
}
