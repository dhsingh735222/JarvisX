"use client";

import { createContext, ReactNode, useContext, useEffect, useState } from "react";
import { api } from "./api";
import { User } from "./types";

interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (data: RegisterPayload) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = "jarvisx_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
    const verification = stored
      ? api
          .get<User>("/api/auth/me", stored)
          .then((u) => {
            setToken(stored);
            setUser(u);
          })
          .catch(() => {
            localStorage.removeItem(STORAGE_KEY);
          })
      : Promise.resolve();
    verification.finally(() => setLoading(false));
  }, []);

  async function login(username: string, password: string) {
    const res = await api.post<AuthResponse>("/api/auth/login", { username, password });
    localStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }

  async function register(data: RegisterPayload) {
    const res = await api.post<AuthResponse>("/api/auth/register", data);
    localStorage.setItem(STORAGE_KEY, res.access_token);
    setToken(res.access_token);
    setUser(res.user);
  }

  function logout() {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
