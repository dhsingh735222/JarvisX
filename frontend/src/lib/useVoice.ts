"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { fetchSpeechAudio, postAudio } from "./api";

export type VoiceStatus = "idle" | "listening" | "recording" | "thinking" | "speaking";

const WAKE_WORDS = ["hey jarvis", "jarvis"];

/* eslint-disable @typescript-eslint/no-explicit-any */
type SpeechRecognitionInstance = any;

function getSpeechRecognitionConstructor(): any {
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
}

function subscribeNever() {
  return () => {};
}

function getWakeWordSupportSnapshot(): boolean {
  return !!getSpeechRecognitionConstructor();
}

function getWakeWordSupportServerSnapshot(): boolean {
  return false;
}

export function useVoiceAssistant(token: string | null, onCommand: (text: string) => void) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [wakeWordActive, setWakeWordActive] = useState(false);
  const wakeWordSupported = useSyncExternalStore(
    subscribeNever,
    getWakeWordSupportSnapshot,
    getWakeWordSupportServerSnapshot
  );
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const onCommandRef = useRef(onCommand);
  const wakeWordActiveRef = useRef(false);
  const pausedForSpeechRef = useRef(false);

  useEffect(() => {
    onCommandRef.current = onCommand;
  }, [onCommand]);

  const startWakeWord = useCallback(() => {
    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (!SpeechRecognition) {
      setError("Wake word listening requires Chrome or Edge");
      return;
    }

    const recognition: SpeechRecognitionInstance = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: any) => {
      const result = event.results[event.results.length - 1];
      if (!result.isFinal) return;
      const transcript = result[0].transcript.trim().toLowerCase();

      const matchedWord = WAKE_WORDS.find((w) => transcript.includes(w));
      if (!matchedWord) return;

      const remainder = transcript.split(matchedWord).pop()?.trim() ?? "";
      if (remainder.length > 2) {
        setStatus("thinking");
        onCommandRef.current(remainder);
      }
    };

    recognition.onerror = (event: any) => {
      if (event.error === "no-speech" || event.error === "aborted") return;
      setError(`Wake word error: ${event.error}`);
    };

    recognition.onend = () => {
      if (wakeWordActiveRef.current && !pausedForSpeechRef.current) {
        try {
          recognition.start();
        } catch {
          /* already started */
        }
      }
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      /* ignore double-start */
    }
    setStatus("listening");
  }, []);

  const toggleWakeWord = useCallback(
    (enabled: boolean) => {
      wakeWordActiveRef.current = enabled;
      setWakeWordActive(enabled);
      setError(null);
      if (enabled) {
        startWakeWord();
      } else {
        pausedForSpeechRef.current = false;
        recognitionRef.current?.stop();
        recognitionRef.current = null;
        setStatus("idle");
      }
    },
    [startWakeWord]
  );

  const speak = useCallback(
    async (text: string) => {
      if (!text) return;
      if (wakeWordActiveRef.current) {
        pausedForSpeechRef.current = true;
        recognitionRef.current?.stop();
      }
      setStatus("speaking");
      try {
        const blob = await fetchSpeechAudio(text, token);
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        await new Promise<void>((resolve) => {
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          audio.play().catch(() => resolve());
        });
        URL.revokeObjectURL(url);
      } catch {
        // Non-fatal: text response is still shown in the chat.
      } finally {
        if (wakeWordActiveRef.current) {
          pausedForSpeechRef.current = false;
          startWakeWord();
        } else {
          setStatus("idle");
        }
      }
    },
    [token, startWakeWord]
  );

  const startRecording = useCallback(async () => {
    setError(null);
    if (wakeWordActiveRef.current) {
      pausedForSpeechRef.current = true;
      recognitionRef.current?.stop();
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setStatus("thinking");
        try {
          const { text } = await postAudio("/api/voice/transcribe", blob, "recording.webm", token);
          if (text.trim()) onCommandRef.current(text.trim());
          else setStatus(wakeWordActiveRef.current ? "listening" : "idle");
        } catch {
          setError("Transcription failed");
          setStatus(wakeWordActiveRef.current ? "listening" : "idle");
        }
        if (wakeWordActiveRef.current) {
          pausedForSpeechRef.current = false;
          startWakeWord();
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setStatus("recording");
    } catch {
      setError("Microphone access denied");
      if (wakeWordActiveRef.current) {
        pausedForSpeechRef.current = false;
        startWakeWord();
      }
    }
  }, [token, startWakeWord]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop();
      mediaRecorderRef.current?.stop();
    };
  }, []);

  return {
    status,
    error,
    wakeWordActive,
    wakeWordSupported,
    toggleWakeWord,
    startRecording,
    stopRecording,
    speak,
    setStatus,
  };
}
