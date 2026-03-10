/**
 * AuthContext - Contexto de autenticacion con info de usuario y rol - v2.0
 * Uses httpOnly cookies (no localStorage token storage)
 * Sliding session: refreshes token every 10 min while active,
 * auto-logout after 30 min of inactivity.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { authAPI } from '../services/api';
import type { UserInfo, UserRole } from '../types';

const INACTIVITY_TIMEOUT = 30 * 60 * 1000; // 30 minutes
const REFRESH_INTERVAL = 10 * 60 * 1000;   // 10 minutes

interface AuthContextType {
  user: UserInfo | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  hasRole: (roles: UserRole[]) => boolean;
  sessionExpiredMessage: string | null;
  clearSessionMessage: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState<string | null>(null);

  const inactivityTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refreshTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastActivity = useRef<number>(Date.now());

  const clearSessionMessage = useCallback(() => {
    setSessionExpiredMessage(null);
  }, []);

  const logout = useCallback(async () => {
    // Stop timers
    if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    if (refreshTimer.current) clearInterval(refreshTimer.current);
    try {
      await authAPI.logout();
    } catch {
      // Server may be unreachable — clear state anyway
    }
    setUser(null);
  }, []);

  const logoutByInactivity = useCallback(async () => {
    if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    if (refreshTimer.current) clearInterval(refreshTimer.current);
    try {
      await authAPI.logout();
    } catch {
      // ignore
    }
    setUser(null);
    setSessionExpiredMessage(
      'Tu sesion se cerro por inactividad. Por favor, inicia sesion nuevamente.'
    );
  }, []);

  const resetInactivityTimer = useCallback(() => {
    lastActivity.current = Date.now();
    if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
    inactivityTimer.current = setTimeout(() => {
      logoutByInactivity();
    }, INACTIVITY_TIMEOUT);
  }, [logoutByInactivity]);

  const startSessionTimers = useCallback(() => {
    // Inactivity timer
    resetInactivityTimer();

    // Refresh interval — renew token every 10 min if user was recently active
    if (refreshTimer.current) clearInterval(refreshTimer.current);
    refreshTimer.current = setInterval(async () => {
      const elapsed = Date.now() - lastActivity.current;
      if (elapsed < INACTIVITY_TIMEOUT) {
        try {
          await authAPI.refreshToken();
        } catch {
          // Token expired server-side or network error → logout
          logoutByInactivity();
        }
      }
    }, REFRESH_INTERVAL);
  }, [resetInactivityTimer, logoutByInactivity]);

  const refreshUser = useCallback(async () => {
    try {
      const userData = await authAPI.getCurrentUser();
      setUser(userData);
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setSessionExpiredMessage(null);
    const response = await authAPI.login(username, password);
    setUser(response.user);
  }, []);

  const hasRole = useCallback((roles: UserRole[]): boolean => {
    if (!user) return false;
    return roles.includes(user.role);
  }, [user]);

  // Start/stop session timers when auth state changes
  useEffect(() => {
    if (!user) return;

    startSessionTimers();

    // Activity events to reset inactivity timer
    const events = ['mousedown', 'keydown', 'scroll', 'touchstart'] as const;
    events.forEach((ev) => document.addEventListener(ev, resetInactivityTimer));

    return () => {
      events.forEach((ev) => document.removeEventListener(ev, resetInactivityTimer));
      if (inactivityTimer.current) clearTimeout(inactivityTimer.current);
      if (refreshTimer.current) clearInterval(refreshTimer.current);
    };
  }, [user, startSessionTimers, resetInactivityTimer]);

  // Listen for session-expired events from axios interceptor
  useEffect(() => {
    const handleSessionExpired = () => {
      logoutByInactivity();
    };
    window.addEventListener('session-expired', handleSessionExpired);
    return () => {
      window.removeEventListener('session-expired', handleSessionExpired);
    };
  }, [logoutByInactivity]);

  // On mount, try to restore session from existing cookie
  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
        refreshUser,
        hasRole,
        sessionExpiredMessage,
        clearSessionMessage,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
