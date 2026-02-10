import { create } from 'zustand';
import type { User } from '@/types';
import { api } from '@/lib/api';

export type LoginPhase = 'idle' | 'warming-up' | 'signing-in';

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  loginPhase: LoginPhase;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  token: typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null,
  isLoading: false,
  isAuthenticated: false,
  error: null,
  loginPhase: 'idle',

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null, loginPhase: 'warming-up' });
    try {
      // Wake the Render backend before sending credentials
      await api.auth.warmUp();

      set({ loginPhase: 'signing-in' });
      const data = await api.auth.login(email, password);
      set({ token: data.access_token });
      try {
        await get().loadUser();
      } catch {
        // loadUser sets its own state; don't let it break login flow
      }
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Login failed',
      });
      throw err;
    } finally {
      set({ isLoading: false, loginPhase: 'idle' });
    }
  },

  register: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      await api.auth.register(email, password);
      await get().login(email, password);
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Registration failed',
      });
      throw err;
    } finally {
      set({ isLoading: false });
    }
  },

  logout: () => {
    api.auth.logout();
    set({ user: null, token: null, isAuthenticated: false });
  },

  loadUser: async () => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    if (!token) {
      set({ isAuthenticated: false, user: null, isLoading: false });
      return;
    }

    set({ isLoading: true });
    try {
      const user = await api.auth.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      set({ user: null, isAuthenticated: false, isLoading: false, token: null });
      api.auth.logout();
    }
  },

  clearError: () => set({ error: null }),
}));
