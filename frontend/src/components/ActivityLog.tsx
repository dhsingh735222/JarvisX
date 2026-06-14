"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ActivityLogEntry } from "@/lib/types";

const STATUS_CLASS: Record<string, string> = {
  success: "text-jarvis-success",
  approved: "text-jarvis-success",
  failed: "text-jarvis-danger",
  denied: "text-jarvis-danger",
  pending: "text-jarvis-warning",
};

export default function ActivityLog() {
  const { token } = useAuth();
  const [logs, setLogs] = useState<ActivityLogEntry[]>([]);

  useEffect(() => {
    if (!token) return;
    let active = true;

    const load = () => {
      api
        .get<ActivityLogEntry[]>("/api/activity?limit=30", token)
        .then((data) => {
          if (active) setLogs(data);
        })
        .catch(() => {});
    };

    load();
    const interval = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [token]);

  return (
    <div className="flex h-full flex-col gap-2 overflow-y-auto pr-1">
      {logs.length === 0 && <p className="text-sm text-jarvis-muted">No activity yet.</p>}
      {logs.map((log) => (
        <div key={log.id} className="rounded-lg border border-jarvis-border bg-jarvis-panel/60 p-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-jarvis-text">{log.tool_name || log.action_type}</span>
            <span className={`shrink-0 uppercase tracking-wide ${STATUS_CLASS[log.status] || "text-jarvis-muted"}`}>
              {log.status}
            </span>
          </div>
          <p className="mt-1 text-jarvis-muted">{new Date(log.created_at).toLocaleTimeString()}</p>
        </div>
      ))}
    </div>
  );
}
