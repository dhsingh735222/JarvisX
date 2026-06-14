import { VoiceStatus } from "@/lib/useVoice";

const STATUS_LABEL: Record<VoiceStatus, string> = {
  idle: "Idle",
  listening: 'Listening for "Jarvis"',
  recording: "Recording...",
  thinking: "Thinking...",
  speaking: "Speaking...",
};

const STATUS_CLASS: Record<VoiceStatus, string> = {
  idle: "border-jarvis-border text-jarvis-muted",
  listening: "border-jarvis-accent text-jarvis-accent bg-jarvis-accent/10 animate-pulse-glow",
  recording: "border-jarvis-danger text-jarvis-danger bg-jarvis-danger/10 animate-pulse-glow",
  thinking: "border-jarvis-accent-2 text-jarvis-accent-2 bg-jarvis-accent-2/10",
  speaking: "border-jarvis-success text-jarvis-success bg-jarvis-success/10",
};

export default function VoiceVisualizer({ status }: { status: VoiceStatus }) {
  return (
    <div className="flex items-center gap-3">
      <div
        className={`relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-2 transition-colors duration-300 ${STATUS_CLASS[status]}`}
      >
        {status === "speaking" || status === "recording" ? (
          <div className="flex h-6 items-end gap-1">
            {[0, 1, 2, 3, 4].map((i) => (
              <span
                key={i}
                className="animate-bar inline-block h-full w-1 rounded-full bg-current"
                style={{ animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
        ) : status === "thinking" ? (
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : (
          <div className="h-3 w-3 rounded-full bg-current" />
        )}
      </div>
      <div>
        <p className="text-sm font-medium text-jarvis-text">JarvisX</p>
        <p className="text-xs uppercase tracking-widest text-jarvis-muted">{STATUS_LABEL[status]}</p>
      </div>
    </div>
  );
}
