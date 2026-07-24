/**
 * Auth store — persists JWT tokens in localStorage so the user stays
 * logged in across refreshes and tabs.
 *
 * BroadcastChannel syncs logout/login across tabs automatically.
 */
import { create } from "zustand";
import { API_BASE_URL } from "@/lib/api";

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  plan: string;
}

interface AuthStore {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isInitialized: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshAccessToken: () => Promise<boolean>;
  initialize: () => Promise<void>;
  getAuthHeaders: () => Record<string, string>;
}

const STORAGE_KEYS = {
  accessToken: "aether.access_token",
  refreshToken: "aether.refresh_token",
};

// Broadcast channel for multi-tab synchronization
const bc = typeof window !== "undefined" ? new BroadcastChannel("aether_auth") : null;

export const useAuthStore = create<AuthStore>((set, get) => ({
  user: null,
  accessToken: typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.accessToken) : null,
  refreshToken: typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEYS.refreshToken) : null,
  isLoading: false,
  isInitialized: false,

  getAuthHeaders: () => {
    const token = get().accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  },

  initialize: async () => {
    const { accessToken, refreshToken } = get();
    if (!accessToken) {
      set({ isInitialized: true });
      return;
    }

    try {
      // Try to load user profile with the stored token
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      if (res.ok) {
        const user = await res.json();
        set({ user, isInitialized: true });
        return;
      }

      // Token expired — try to refresh
      if (res.status === 401 && refreshToken) {
        const refreshed = await get().refreshAccessToken();
        if (!refreshed) {
          // Refresh failed — clear tokens
          localStorage.removeItem(STORAGE_KEYS.accessToken);
          localStorage.removeItem(STORAGE_KEYS.refreshToken);
          set({ user: null, accessToken: null, refreshToken: null, isInitialized: true });
        }
        return;
      }

      // Any other error — clear
      localStorage.removeItem(STORAGE_KEYS.accessToken);
      localStorage.removeItem(STORAGE_KEYS.refreshToken);
      set({ user: null, accessToken: null, refreshToken: null, isInitialized: true });
    } catch {
      // Network offline — keep tokens, mark initialized
      set({ isInitialized: true });
    }
  },

  refreshAccessToken: async () => {
    const { refreshToken } = get();
    if (!refreshToken) return false;

    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) return false;

      const data = await res.json();
      localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
      localStorage.setItem(STORAGE_KEYS.refreshToken, data.refresh_token);

      // Load profile with new token
      const profileRes = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });

      if (profileRes.ok) {
        const user = await profileRes.json();
        set({ user, accessToken: data.access_token, refreshToken: data.refresh_token, isInitialized: true });
        return true;
      }

      return false;
    } catch {
      return false;
    }
  },

  login: async (email, password) => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Invalid email or password");
      }

      const data = await res.json();
      localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
      localStorage.setItem(STORAGE_KEYS.refreshToken, data.refresh_token);

      // Load user profile
      const profileRes = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const user = await profileRes.json();

      set({ user, accessToken: data.access_token, refreshToken: data.refresh_token, isLoading: false });

      // Clear any in-memory guest sessions so they never appear in this
      // authenticated user's dashboard.
      try {
        const { useResearchStore } = await import("@/store/research");
        useResearchStore.getState().clearGuestSessions();
      } catch { /* ignore */ }

      bc?.postMessage({ type: "login" });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  register: async (name, email, password) => {
    set({ isLoading: true });
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Registration failed");
      }

      const data = await res.json();
      localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
      localStorage.setItem(STORAGE_KEYS.refreshToken, data.refresh_token);

      const profileRes = await fetch(`${API_BASE_URL}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      const user = await profileRes.json();

      set({ user, accessToken: data.access_token, refreshToken: data.refresh_token, isLoading: false });

      // Clear any in-memory guest sessions so they never appear in this
      // newly-registered user's dashboard.
      try {
        const { useResearchStore } = await import("@/store/research");
        useResearchStore.getState().clearGuestSessions();
      } catch { /* ignore */ }

      bc?.postMessage({ type: "login" });
    } catch (err) {
      set({ isLoading: false });
      throw err;
    }
  },

  logout: async () => {
    const { accessToken } = get();
    try {
      if (accessToken) {
        await fetch(`${API_BASE_URL}/api/v1/auth/logout`, {
          method: "POST",
          headers: { Authorization: `Bearer ${accessToken}` },
        });
      }
    } catch {
      // Best-effort logout — clear client state regardless of server response
    } finally {
      // Clear all auth tokens
      localStorage.removeItem(STORAGE_KEYS.accessToken);
      localStorage.removeItem(STORAGE_KEYS.refreshToken);
      // Clear any other app state in localStorage
      localStorage.removeItem("aether.apiBaseUrl");
      // Clear sessionStorage
      if (typeof window !== "undefined") {
        sessionStorage.clear();
      }
      // Reset Zustand auth state
      set({ user: null, accessToken: null, refreshToken: null, isInitialized: true });
      // Clear research sessions from store so no data leaks to next user
      try {
        const { useResearchStore } = await import("@/store/research");
        useResearchStore.setState({ sessions: [], current: null, error: null });
      } catch { /* ignore */ }
      // Notify other tabs
      bc?.postMessage({ type: "logout" });
      // Redirect this tab to login (replace history so back button can't return)
      if (typeof window !== "undefined") {
        window.location.replace("/login");
      }
    }
  },
}));

// Listen for auth events from other tabs
if (typeof window !== "undefined" && bc) {
  bc.onmessage = (event) => {
    if (event.data.type === "logout") {
      localStorage.removeItem(STORAGE_KEYS.accessToken);
      localStorage.removeItem(STORAGE_KEYS.refreshToken);
      useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
      window.location.href = "/login";
    }
    if (event.data.type === "login") {
      useAuthStore.getState().initialize();
    }
  };
}
