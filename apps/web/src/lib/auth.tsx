"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, ApiError, TOKEN_KEY } from "./api";
import type { TokenResponse, User } from "./types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (input: {
    username: string;
    email: string;
    password: string;
    full_name?: string;
  }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const logout = useCallback(() => {
    window.localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    router.replace("/login");
  }, [router]);

  useEffect(() => {
    const token = window.localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {
        window.localStorage.removeItem(TOKEN_KEY);
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onUnauthorized = () => logout();
    window.addEventListener("veridex:unauthorized", onUnauthorized);
    return () =>
      window.removeEventListener("veridex:unauthorized", onUnauthorized);
  }, [logout]);

  const login = useCallback(
    async (username: string, password: string) => {
      const res = await api<TokenResponse>("/auth/login", {
        method: "POST",
        json: { username, password },
      });
      window.localStorage.setItem(TOKEN_KEY, res.access_token);
      const me = await api<User>("/auth/me");
      setUser(me);
      router.replace("/dashboard");
    },
    [router],
  );

  const register = useCallback(
    async (input: {
      username: string;
      email: string;
      password: string;
      full_name?: string;
    }) => {
      await api<{ id: string }>("/auth/register", {
        method: "POST",
        json: { ...input, role: "officer" },
      });
      await login(input.username, input.password);
    },
    [login],
  );

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { ApiError };

export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong";
}