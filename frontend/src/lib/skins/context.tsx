"use client";

import React, { createContext, useContext } from "react";
import type { SkinRenderer } from "./types";
import { defaultSkinRenderer } from "./default-skin";
import { getSkinRenderer } from "./registry";
import { useSkinStore } from "../../store/skin";

const SkinContext = createContext<SkinRenderer>(defaultSkinRenderer);

export function SkinProvider({ children }: { children: React.ReactNode }) {
  const activeSkinId = useSkinStore((s) => s.activeSkinId);
  return (
    <SkinContext.Provider value={getSkinRenderer(activeSkinId)}>
      {children}
    </SkinContext.Provider>
  );
}

export function useActiveSkinRenderer(): SkinRenderer {
  return useContext(SkinContext);
}
