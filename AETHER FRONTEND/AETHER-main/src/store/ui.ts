import { create } from "zustand";
import { API_BASE_URL } from "@/lib/api";

interface UIStore {
  commandOpen: boolean;
  setCommandOpen: (v: boolean) => void;
  toggleCommand: () => void;
  reasoningOpen: boolean;
  toggleReasoning: () => void;
  apiBaseUrl: string;
  setApiBaseUrl: (v: string) => void;
}

export const useUIStore = create<UIStore>((set) => ({
  commandOpen: false,
  setCommandOpen: (v) => set({ commandOpen: v }),
  toggleCommand: () => set((s) => ({ commandOpen: !s.commandOpen })),
  reasoningOpen: false,
  toggleReasoning: () => set((s) => ({ reasoningOpen: !s.reasoningOpen })),
  // Initialise from api.ts so there is exactly one source of truth
  apiBaseUrl: API_BASE_URL,
  setApiBaseUrl: (v) => {
    if (typeof window !== "undefined") localStorage.setItem("aether.apiBaseUrl", v);
    set({ apiBaseUrl: v });
  },
}));
