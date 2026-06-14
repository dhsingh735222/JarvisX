"use client";

import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ChatResponse, Message, PendingAction } from "@/lib/types";
import { useVoiceAssistant } from "@/lib/useVoice";
import ApprovalModal from "./ApprovalModal";
import VoiceVisualizer from "./VoiceVisualizer";

function isVisible(m: Message): boolean {
  return (m.role === "user" || m.role === "assistant") && m.content.trim().length > 0;
}

export default function ChatPanel() {
  const { token } = useAuth();
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);
  const [sending, setSending] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sendMessageRef = useRef<(text: string) => void>(() => {});

  const voice = useVoiceAssistant(token, (text) => sendMessageRef.current(text));

  function handleResult(result: ChatResponse) {
    setConversationId(result.conversation_id);
    setMessages((prev) => [...prev, ...result.messages]);
    setPendingAction(result.pending_action);

    if (voiceReplies && !result.pending_action) {
      const lastAssistant = [...result.messages].reverse().find((m) => m.role === "assistant" && m.content.trim());
      if (lastAssistant) void voice.speak(lastAssistant.content);
    }
  }

  async function sendMessage(text: string) {
    if (!text.trim() || !token || sending) return;
    const userMsg: Message = {
      id: Date.now(),
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    try {
      const result = await api.post<ChatResponse>(
        "/api/chat",
        { message: text, conversation_id: conversationId },
        token
      );
      handleResult(result);
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "Could not reach the JarvisX backend.";
      setMessages((prev) => [
        ...prev,
        { id: Date.now() + 1, role: "assistant", content: `⚠️ ${detail}`, created_at: new Date().toISOString() },
      ]);
      voice.setStatus(voice.wakeWordActive ? "listening" : "idle");
    } finally {
      setSending(false);
    }
  }

  useEffect(() => {
    sendMessageRef.current = sendMessage;
  });

  async function resolveApproval(approve: boolean) {
    if (!pendingAction || !conversationId || !token) return;
    setSending(true);
    try {
      const result = await api.post<ChatResponse>(
        `/api/conversations/${conversationId}/approvals/${pendingAction.id}`,
        { approve },
        token
      );
      setPendingAction(null);
      handleResult(result);
    } finally {
      setSending(false);
    }
  }

  function newChat() {
    setConversationId(null);
    setMessages([]);
    setPendingAction(null);
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <VoiceVisualizer status={voice.status} />
        <div className="flex items-center gap-3 text-sm">
          <label className="flex items-center gap-2 text-jarvis-muted">
            <input
              type="checkbox"
              checked={voiceReplies}
              onChange={(e) => setVoiceReplies(e.target.checked)}
              className="accent-jarvis-accent"
            />
            Voice replies
          </label>
          <button
            onClick={() => voice.toggleWakeWord(!voice.wakeWordActive)}
            disabled={!voice.wakeWordSupported}
            className={`rounded-full border px-3 py-1 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
              voice.wakeWordActive
                ? "border-jarvis-accent text-jarvis-accent"
                : "border-jarvis-border text-jarvis-muted"
            }`}
          >
            {voice.wakeWordActive ? 'Wake word: ON ("Jarvis")' : "Wake word: OFF"}
          </button>
          <button
            onClick={newChat}
            className="rounded-full border border-jarvis-border px-3 py-1 text-xs font-medium text-jarvis-muted transition hover:text-jarvis-text"
          >
            New chat
          </button>
        </div>
      </div>

      {voice.error && (
        <p className="flex items-start gap-2 text-xs text-jarvis-danger">
          <span className="flex-1">{voice.error}</span>
          <button
            onClick={voice.clearError}
            className="shrink-0 text-jarvis-muted hover:text-jarvis-text"
            title="Dismiss"
          >
            ✕
          </button>
        </p>
      )}
      {!voice.wakeWordSupported && (
        <p className="text-xs text-jarvis-muted">
          Continuous wake-word listening needs Chrome or Edge. You can still use the mic button below.
        </p>
      )}

      <div
        ref={scrollRef}
        className="flex-1 space-y-3 overflow-y-auto rounded-2xl border border-jarvis-border bg-jarvis-panel/40 p-4"
      >
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center text-jarvis-muted">
            <p className="text-lg font-medium text-jarvis-text">Hey, I&apos;m JarvisX.</p>
            <p className="mt-1 max-w-sm text-sm">
              Ask me to manage files, open apps, search the web, or just chat. Say &quot;Jarvis&quot; or use the mic
              to talk to me.
            </p>
          </div>
        )}
        {messages.filter(isVisible).map((m) => (
          <div
            key={m.id}
            className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm whitespace-pre-wrap ${
              m.role === "user"
                ? "ml-auto bg-jarvis-accent text-black"
                : "bg-jarvis-panel-2 text-jarvis-text border border-jarvis-border"
            }`}
          >
            {m.content}
          </div>
        ))}
        {sending && <div className="text-xs text-jarvis-muted">JarvisX is thinking...</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void sendMessage(input);
        }}
        className="flex items-center gap-2"
      >
        <button
          type="button"
          onMouseDown={() => void voice.startRecording()}
          onMouseUp={voice.stopRecording}
          onTouchStart={(e) => {
            e.preventDefault();
            void voice.startRecording();
          }}
          onTouchEnd={voice.stopRecording}
          className={`shrink-0 rounded-full border px-4 py-2 text-sm transition ${
            voice.status === "recording"
              ? "border-jarvis-danger text-jarvis-danger animate-pulse-glow"
              : "border-jarvis-border text-jarvis-text hover:border-jarvis-accent"
          }`}
          title="Hold to talk"
        >
          🎤 Hold to talk
        </button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask JarvisX anything..."
          className="flex-1 rounded-full border border-jarvis-border bg-jarvis-panel px-4 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="shrink-0 rounded-full bg-jarvis-accent px-5 py-2 text-sm font-medium text-black transition disabled:opacity-50"
        >
          Send
        </button>
      </form>

      {pendingAction && <ApprovalModal action={pendingAction} busy={sending} onResolve={resolveApproval} />}
    </div>
  );
}
