import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '../types/auth';

interface AuthContextValue {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

function isTokenExpired(payload: Record<string, unknown>): boolean {
  const exp = payload.exp as number | undefined;
  if (!exp) return false;
  return Date.now() / 1000 > exp;
}

function extractUser(payload: Record<string, unknown>): User | null {
  const user_id = payload.sub as string | undefined;
  if (!user_id) return null;
  return {
    user_id,
    email: (payload.email as string) || '',
    username: (payload.username as string) || '',
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('auth_token') || import.meta.env.VITE_DEV_TOKEN || null;
    if (stored) {
      const payload = decodeJwtPayload(stored);
      if (payload && !isTokenExpired(payload)) {
        setToken(stored);
        setUser(extractUser(payload));
        localStorage.setItem('auth_token', stored);
      } else {
        localStorage.removeItem('auth_token');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback((newToken: string) => {
    const payload = decodeJwtPayload(newToken);
    if (!payload) return;
    if (isTokenExpired(payload)) return;
    localStorage.setItem('auth_token', newToken);
    setToken(newToken);
    setUser(extractUser(payload));
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('auth_token');
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated: !!token,
        loading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
