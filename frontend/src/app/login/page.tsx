"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, loading, login, register } = useAuth();
  const router = useRouter();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [checkingSetup, setCheckingSetup] = useState(true);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    api
      .get<{ setup_required: boolean }>("/api/auth/setup-required")
      .then((res) => setMode(res.setup_required ? "register" : "login"))
      .catch(() => {})
      .finally(() => setCheckingSetup(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") {
        await register({ username, email, password, full_name: fullName || undefined });
      } else {
        await login(username, password);
      }
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Is the backend running?");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading || checkingSetup || user) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-jarvis-accent border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="flex flex-1 items-center justify-center p-4">
      <div className="w-full max-w-sm rounded-2xl border border-jarvis-border bg-jarvis-panel/60 p-8 shadow-2xl">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 h-3 w-3 rounded-full bg-jarvis-accent shadow-[0_0_16px_4px_rgba(56,225,255,0.6)]" />
          <h1 className="text-2xl font-semibold tracking-wide text-jarvis-text">JarvisX</h1>
          <p className="mt-1 text-sm text-jarvis-muted">
            {mode === "register" ? "Create your operator account" : "Sign in to your assistant"}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-jarvis-muted">Username</label>
            <input
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
              autoComplete="username"
            />
          </div>

          {mode === "register" && (
            <>
              <div>
                <label className="mb-1 block text-xs text-jarvis-muted">Email</label>
                <input
                  required
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
                  autoComplete="email"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-jarvis-muted">Full name (optional)</label>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
                  autoComplete="name"
                />
              </div>
            </>
          )}

          <div>
            <label className="mb-1 block text-xs text-jarvis-muted">Password</label>
            <input
              required
              type="password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
              autoComplete={mode === "register" ? "new-password" : "current-password"}
            />
          </div>

          {error && <p className="text-xs text-jarvis-danger">{error}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-full bg-jarvis-accent px-4 py-2 text-sm font-medium text-black transition disabled:opacity-50"
          >
            {submitting ? "Please wait..." : mode === "register" ? "Create account" : "Sign in"}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-jarvis-muted">
          {mode === "register" ? "Already have an account?" : "Need an account?"}{" "}
          <button
            onClick={() => {
              setError(null);
              setMode(mode === "register" ? "login" : "register");
            }}
            className="text-jarvis-accent hover:underline"
          >
            {mode === "register" ? "Sign in" : "Register"}
          </button>
        </p>
      </div>
    </div>
  );
}
