'use client';

import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export type ToastVariant = 'default' | 'success' | 'error' | 'info';

export interface ToastItem {
  id: string;
  title?: string;
  description?: string;
  variant?: ToastVariant;
  duration?: number;
}

interface ToastContextType {
  toast: (options: Omit<ToastItem, 'id'>) => void;
  success: (description: string, title?: string) => void;
  error: (description: string, title?: string) => void;
  info: (description: string, title?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    ({ title, description, variant = 'default', duration = 3500 }: Omit<ToastItem, 'id'>) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      const newToast: ToastItem = { id, title, description, variant, duration };

      setToasts((prev) => [...prev.slice(-3), newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback(
    (description: string, title = 'Succès') => {
      addToast({ title, description, variant: 'success' });
    },
    [addToast]
  );

  const error = useCallback(
    (description: string, title = 'Erreur') => {
      addToast({ title, description, variant: 'error' });
    },
    [addToast]
  );

  const info = useCallback(
    (description: string, title = 'Information') => {
      addToast({ title, description, variant: 'info' });
    },
    [addToast]
  );

  return (
    <ToastContext.Provider value={{ toast: addToast, success, error, info }}>
      {children}
      {/* Toast Notification Container */}
      <div
        role="region"
        aria-label="Notifications"
        className="fixed bottom-20 md:bottom-6 right-4 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none"
      >
        {toasts.map((item) => (
          <div
            key={item.id}
            role="status"
            className={`pointer-events-auto flex items-start gap-3 p-3.5 rounded-xl border backdrop-blur-2xl shadow-2xl transition-all duration-300 animate-in slide-in-from-bottom-3 fade-in ${
              item.variant === 'success'
                ? 'bg-emerald-950/80 border-emerald-500/30 text-emerald-200'
                : item.variant === 'error'
                ? 'bg-rose-950/80 border-rose-500/30 text-rose-200'
                : item.variant === 'info'
                ? 'bg-sky-950/80 border-sky-500/30 text-sky-200'
                : 'bg-zinc-900/90 border-white/[0.14] text-white'
            }`}
          >
            <div className="shrink-0 mt-0.5">
              {item.variant === 'success' && <CheckCircle2 className="h-4 w-4 text-emerald-400" />}
              {item.variant === 'error' && <AlertCircle className="h-4 w-4 text-rose-400" />}
              {item.variant === 'info' && <Info className="h-4 w-4 text-sky-400" />}
              {item.variant === 'default' && <Info className="h-4 w-4 text-zinc-300" />}
            </div>

            <div className="flex-1 min-w-0">
              {item.title && (
                <div className="text-xs font-semibold tracking-tight text-white mb-0.5">
                  {item.title}
                </div>
              )}
              {item.description && (
                <div className="text-xs text-zinc-300 leading-relaxed font-normal">
                  {item.description}
                </div>
              )}
            </div>

            <button
              onClick={() => removeToast(item.id)}
              className="p-1 rounded-lg text-zinc-400 hover:text-white transition-colors cursor-pointer shrink-0"
              aria-label="Fermer la notification"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
