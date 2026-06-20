import { create } from 'zustand';
import { User } from '@/types';
import { authApi } from '@/services/api';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: localStorage.getItem('access_token') || null,
  refreshToken: localStorage.getItem('refresh_token') || null,
  isAuthenticated: !!localStorage.getItem('access_token'),
  isLoading: false,

  login: async (username, password) => {
    set({ isLoading: true });
    try {
      const response = await authApi.login({ username, password });
      localStorage.setItem('access_token', response.access_token);
      localStorage.setItem('refresh_token', response.refresh_token);
      set({
        user: response.user,
        accessToken: response.access_token,
        refreshToken: response.refresh_token,
        isAuthenticated: true,
      });
    } finally {
      set({ isLoading: false });
    }
  },

  logout: () => {
    authApi.logout();
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
    });
  },

  checkAuth: () => {
    const token = localStorage.getItem('access_token');
    if (token) {
      set({ isAuthenticated: true });
    } else {
      set({ isAuthenticated: false });
    }
  },
}));

interface AppState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
