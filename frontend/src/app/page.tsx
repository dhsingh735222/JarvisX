"use client";

import { useState } from "react";
import ActivityLog from "@/components/ActivityLog";
import AppShell from "@/components/AppShell";
import ChatPanel from "@/components/ChatPanel";
import MemoryViewer from "@/components/MemoryViewer";

type SidebarTab = "activity" | "memory";

export default function Home() {
  const [tab, setTab] = useState<SidebarTab>("activity");

  return (
    <AppShell>
      <div className="grid flex-1 gap-4 lg:grid-cols-[1fr_320px]">
        <section className="flex min-h-[60vh] flex-col rounded-2xl border border-jarvis-border bg-jarvis-panel/30 p-4 lg:min-h-0">
          <ChatPanel />
        </section>
        <aside className="flex min-h-[40vh] flex-col rounded-2xl border border-jarvis-border bg-jarvis-panel/30 p-4 lg:min-h-0">
          <div className="mb-3 flex gap-2 text-sm">
            <button
              onClick={() => setTab("activity")}
              className={`rounded-full px-3 py-1 transition ${
                tab === "activity"
                  ? "bg-jarvis-accent text-black"
                  : "border border-jarvis-border text-jarvis-muted hover:text-jarvis-text"
              }`}
            >
              Activity
            </button>
            <button
              onClick={() => setTab("memory")}
              className={`rounded-full px-3 py-1 transition ${
                tab === "memory"
                  ? "bg-jarvis-accent text-black"
                  : "border border-jarvis-border text-jarvis-muted hover:text-jarvis-text"
              }`}
            >
              Memory
            </button>
          </div>
          <div className="flex-1 overflow-hidden">{tab === "activity" ? <ActivityLog /> : <MemoryViewer />}</div>
        </aside>
      </div>
    </AppShell>
  );
}
