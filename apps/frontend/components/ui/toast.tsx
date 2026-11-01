"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { cn } from "./cn";
import { Check, AlertTriangle, Info, X } from "./icons";

type ToastTone = "success" | "error" | "info";
interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastContextValue {
  toast: (message: string, tone?: ToastTone) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <ToastProvider>");
  return ctx;
}

const TONE_STYLES: Record<ToastTone, { cls: string; icon: React.ReactNode }> = {
  success: { cls: "border-success/30", icon: <Check className="w-4 h-4 text-success" /> },
  error: { cls: "border-danger/30", icon: <AlertTriangle className="w-4 h-4 text-danger" /> },
  info: { cls: "border-info/30", icon: <Info className="w-4 h-4 text-info" /> },
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [mounted, setMounted] = useState(false);
  const nextId = useRef(1);

  useEffect(() => setMounted(true), []);

  const remove = useCallback((id: number) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (message: string, tone: ToastTone = "info") => {
      const id = nextId.current++;
      setToasts((t) => [...t, { id, tone, message }]);
      setTimeout(() => remove(id), 5000);
    },
    [remove],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toast: push,
      success: (m) => push(m, "success"),
      error: (m) => push(m, "error"),
      info: (m) => push(m, "info"),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      {mounted &&
        createPortal(
          <div
            className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 w-[min(92vw,22rem)]"
            role="region"
            aria-label="Notifications"
          >
            {toasts.map((t) => (
              <div
                key={t.id}
                role="status"
                className={cn(
                  "flex items-start gap-3 bg-surface border rounded-lg shadow-lg px-4 py-3",
                  "animate-[saha-toast-in_180ms_ease-out]",
                  TONE_STYLES[t.tone].cls,
                )}
              >
                <span className="mt-0.5 shrink-0">{TONE_STYLES[t.tone].icon}</span>
                <p className="text-sm text-ink flex-1">{t.message}</p>
                <button
                  onClick={() => remove(t.id)}
                  className="text-muted hover:text-ink shrink-0"
                  aria-label="Dismiss notification"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  );
}
