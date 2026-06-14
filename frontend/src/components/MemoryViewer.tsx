"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { MemoryItem } from "@/lib/types";

export default function MemoryViewer() {
  const { token } = useAuth();
  const [items, setItems] = useState<MemoryItem[]>([]);

  const load = useCallback(() => {
    if (!token) return;
    api
      .get<MemoryItem[]>("/api/memory", token)
      .then(setItems)
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function remove(id: number) {
    await api.delete(`/api/memory/${id}`, token);
    load();
  }

  return (
    <div className="flex h-full flex-col gap-2 overflow-y-auto pr-1">
      {items.length === 0 && (
        <p className="text-sm text-jarvis-muted">JarvisX hasn&apos;t learned anything about you yet.</p>
      )}
      {items.map((item) => (
        <div key={item.id} className="rounded-lg border border-jarvis-border bg-jarvis-panel/60 p-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="rounded bg-jarvis-accent/10 px-2 py-0.5 font-medium text-jarvis-accent">
              {item.category}
            </span>
            <button onClick={() => remove(item.id)} className="text-jarvis-muted hover:text-jarvis-danger">
              Remove
            </button>
          </div>
          <p className="mt-1 font-medium text-jarvis-text">{item.key}</p>
          <p className="text-jarvis-muted">{item.value}</p>
        </div>
      ))}
    </div>
  );
}
