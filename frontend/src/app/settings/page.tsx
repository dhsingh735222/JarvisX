"use client";

import { useCallback, useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { SettingsData } from "@/lib/types";

const LLM_PROVIDERS = [
  { id: "anthropic", label: "Anthropic (Claude)", defaultModel: "claude-sonnet-4-5" },
  { id: "openai", label: "OpenAI (GPT)", defaultModel: "gpt-4o" },
  { id: "google", label: "Google (Gemini)", defaultModel: "gemini-2.0-flash" },
  { id: "ollama", label: "Ollama (local model)", defaultModel: "llama3.1" },
];

const TTS_ENGINES = [
  { id: "pyttsx3", label: "Pyttsx3 (offline, built-in)" },
  { id: "elevenlabs", label: "ElevenLabs (requires API key)" },
  { id: "openai", label: "OpenAI TTS (requires API key)" },
];

const API_KEY_PROVIDERS = [
  { id: "anthropic", label: "Anthropic API key" },
  { id: "openai", label: "OpenAI API key" },
  { id: "google", label: "Google AI API key" },
  { id: "elevenlabs", label: "ElevenLabs API key" },
];

export default function SettingsPage() {
  const { token } = useAuth();
  const [data, setData] = useState<SettingsData | null>(null);
  const [workspaceRoot, setWorkspaceRoot] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [keyInputs, setKeyInputs] = useState<Record<string, string>>({});

  const load = useCallback(() => {
    if (!token) return;
    api
      .get<SettingsData>("/api/settings", token)
      .then(setData)
      .catch(() => setError("Could not load settings."));
    api
      .get<{ workspace_root: string }>("/api/settings/workspace", token)
      .then((r) => setWorkspaceRoot(r.workspace_root))
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  async function saveSettings(patch: Partial<Pick<SettingsData, "llm_provider" | "llm_model" | "tts_engine">>) {
    if (!token || !data) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      const updated = await api.put<SettingsData>("/api/settings", patch, token);
      setData(updated);
      setMessage("Settings saved.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save settings.");
    } finally {
      setSaving(false);
    }
  }

  async function saveApiKey(provider: string) {
    const value = keyInputs[provider]?.trim();
    if (!token || !value) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await api.put("/api/settings/api-keys", { provider, value }, token);
      setKeyInputs((prev) => ({ ...prev, [provider]: "" }));
      setMessage(`${provider} key saved.`);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to save API key.");
    } finally {
      setSaving(false);
    }
  }

  async function removeApiKey(provider: string) {
    if (!token) return;
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await api.delete(`/api/settings/api-keys/${provider}`, token);
      setMessage(`${provider} key removed.`);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Failed to remove API key.");
    } finally {
      setSaving(false);
    }
  }

  if (!data) {
    return (
      <AppShell>
        <div className="flex flex-1 items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-jarvis-accent border-t-transparent" />
        </div>
      </AppShell>
    );
  }

  const configuredKeys = new Map(data.api_keys.map((k) => [k.provider, k]));

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6 pb-10">
        <h1 className="text-xl font-semibold text-jarvis-text">Settings</h1>

        {message && <p className="rounded-lg border border-jarvis-success/40 bg-jarvis-success/10 px-3 py-2 text-sm text-jarvis-success">{message}</p>}
        {error && <p className="rounded-lg border border-jarvis-danger/40 bg-jarvis-danger/10 px-3 py-2 text-sm text-jarvis-danger">{error}</p>}

        <section className="rounded-2xl border border-jarvis-border bg-jarvis-panel/40 p-5">
          <h2 className="text-sm font-semibold text-jarvis-text">AI model</h2>
          <p className="mt-1 text-xs text-jarvis-muted">
            Choose which AI provider and model JarvisX uses to think and respond.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs text-jarvis-muted">Provider</label>
              <select
                value={data.llm_provider}
                onChange={(e) => {
                  const provider = e.target.value;
                  const def = LLM_PROVIDERS.find((p) => p.id === provider)?.defaultModel ?? "";
                  setData({ ...data, llm_provider: provider, llm_model: def });
                  saveSettings({ llm_provider: provider, llm_model: def });
                }}
                className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
              >
                {LLM_PROVIDERS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-jarvis-muted">Model</label>
              <input
                value={data.llm_model}
                onChange={(e) => setData({ ...data, llm_model: e.target.value })}
                onBlur={() => saveSettings({ llm_model: data.llm_model })}
                className="w-full rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
              />
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-jarvis-border bg-jarvis-panel/40 p-5">
          <h2 className="text-sm font-semibold text-jarvis-text">Voice (text-to-speech)</h2>
          <p className="mt-1 text-xs text-jarvis-muted">Pick how JarvisX speaks its replies.</p>
          <div className="mt-4">
            <select
              value={data.tts_engine}
              onChange={(e) => {
                setData({ ...data, tts_engine: e.target.value });
                saveSettings({ tts_engine: e.target.value });
              }}
              className="w-full max-w-xs rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
            >
              {TTS_ENGINES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </section>

        <section className="rounded-2xl border border-jarvis-border bg-jarvis-panel/40 p-5">
          <h2 className="text-sm font-semibold text-jarvis-text">API keys</h2>
          <p className="mt-1 text-xs text-jarvis-muted">
            Keys are encrypted at rest and only used to call the corresponding provider on your behalf.
          </p>
          <div className="mt-4 space-y-3">
            {API_KEY_PROVIDERS.map((p) => {
              const status = configuredKeys.get(p.id);
              return (
                <div key={p.id} className="flex items-center gap-2">
                  <div className="w-40 shrink-0 text-sm text-jarvis-text">{p.label}</div>
                  <input
                    type="password"
                    placeholder={status?.configured ? "•••••••• (configured)" : "Not set"}
                    value={keyInputs[p.id] ?? ""}
                    onChange={(e) => setKeyInputs((prev) => ({ ...prev, [p.id]: e.target.value }))}
                    className="flex-1 rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-sm focus:border-jarvis-accent focus:outline-none"
                  />
                  <button
                    disabled={saving || !keyInputs[p.id]?.trim()}
                    onClick={() => saveApiKey(p.id)}
                    className="rounded-lg bg-jarvis-accent px-3 py-2 text-xs font-medium text-black transition disabled:opacity-50"
                  >
                    Save
                  </button>
                  {status?.configured && (
                    <button
                      disabled={saving}
                      onClick={() => removeApiKey(p.id)}
                      className="rounded-lg border border-jarvis-border px-3 py-2 text-xs text-jarvis-muted transition hover:border-jarvis-danger hover:text-jarvis-danger disabled:opacity-50"
                    >
                      Remove
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </section>

        <section className="rounded-2xl border border-jarvis-border bg-jarvis-panel/40 p-5">
          <h2 className="text-sm font-semibold text-jarvis-text">Workspace</h2>
          <p className="mt-1 text-xs text-jarvis-muted">
            JarvisX can only read, write, and manage files inside this folder. File-operation tools that rename,
            move, or delete anything require your approval.
          </p>
          <code className="mt-3 block break-all rounded-lg border border-jarvis-border bg-jarvis-bg px-3 py-2 text-xs text-jarvis-accent">
            {workspaceRoot ?? "Loading..."}
          </code>
        </section>
      </div>
    </AppShell>
  );
}
