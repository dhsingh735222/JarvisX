"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect } from "react";
import { useAuth } from "@/lib/auth";

export default function AppShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-jarvis-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-jarvis-border px-6 py-3">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-jarvis-accent shadow-[0_0_12px_3px_rgba(56,225,255,0.6)]" />
            <span className="text-lg font-semibold tracking-wide text-jarvis-text">JarvisX</span>
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link
              href="/"
              className={pathname === "/" ? "text-jarvis-accent" : "text-jarvis-muted hover:text-jarvis-text"}
            >
              Dashboard
            </Link>
            <Link
              href="/settings"
              className={
                pathname === "/settings" ? "text-jarvis-accent" : "text-jarvis-muted hover:text-jarvis-text"
              }
            >
              Settings
            </Link>
          </nav>
        </div>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-jarvis-muted">{user.full_name || user.username}</span>
          <button
            onClick={() => {
              logout();
              router.replace("/login");
            }}
            className="rounded-full border border-jarvis-border px-3 py-1 text-xs text-jarvis-muted transition hover:border-jarvis-danger hover:text-jarvis-danger"
          >
            Log out
          </button>
        </div>
      </header>
      <main className="flex flex-1 flex-col p-4 md:p-6">{children}</main>
    </div>
  );
}
