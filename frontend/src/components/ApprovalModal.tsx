import { PendingAction } from "@/lib/types";

interface Props {
  action: PendingAction;
  busy: boolean;
  onResolve: (approve: boolean) => void;
}

const TOOL_LABELS: Record<string, string> = {
  rename_path: "Rename a file or folder",
  move_path: "Move a file or folder",
  delete_path: "Delete a file or folder",
};

export default function ApprovalModal({ action, busy, onResolve }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-jarvis-border bg-jarvis-panel p-6 shadow-2xl">
        <div className="flex items-center gap-2">
          <span className="text-2xl">⚠️</span>
          <h2 className="text-lg font-semibold text-jarvis-warning">Approval required</h2>
        </div>
        <p className="mt-3 text-sm text-jarvis-muted">
          JarvisX wants to{" "}
          <span className="font-semibold text-jarvis-text">
            {TOOL_LABELS[action.tool_name] || action.tool_name}
          </span>
          . Review the details below before allowing this action.
        </p>
        <pre className="mt-3 max-h-48 overflow-auto rounded-lg border border-jarvis-border bg-black/40 p-3 text-xs text-jarvis-text">
          {JSON.stringify(action.tool_input, null, 2)}
        </pre>
        <div className="mt-5 flex justify-end gap-3">
          <button
            disabled={busy}
            onClick={() => onResolve(false)}
            className="rounded-lg border border-jarvis-border px-4 py-2 text-sm font-medium text-jarvis-text transition hover:bg-white/5 disabled:opacity-50"
          >
            Deny
          </button>
          <button
            disabled={busy}
            onClick={() => onResolve(true)}
            className="rounded-lg bg-jarvis-accent px-4 py-2 text-sm font-medium text-black transition hover:opacity-90 disabled:opacity-50"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
