'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

export interface TelegramUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
}

interface TelegramContextType {
  isTWA: boolean;
  user: TelegramUser | null;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

const TelegramContext = createContext<TelegramContextType>({
  isTWA: false,
  user: null,
  triggerHaptic: () => {},
});

export const TelegramProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isTWA] = useState<boolean>(() => {
    if (typeof window !== 'undefined') {
      const tg = (window as unknown as { Telegram?: { WebApp?: unknown } })?.Telegram?.WebApp;
      return Boolean(tg);
    }
    return false;
  });

  const [user] = useState<TelegramUser | null>(() => {
    if (typeof window !== 'undefined') {
      const tg = (window as unknown as { Telegram?: { WebApp?: { initDataUnsafe?: { user?: TelegramUser } } } })?.Telegram?.WebApp;
      return tg?.initDataUnsafe?.user || null;
    }
    return null;
  });

  useEffect(() => {
    // Notify Telegram that Mini App is ready and expand viewport
    if (typeof window !== 'undefined') {
      const tg = (window as unknown as { Telegram?: { WebApp?: { ready: () => void; expand: () => void } } })?.Telegram?.WebApp;
      if (tg) {
        try {
          tg.ready();
          tg.expand();
        } catch {
          // ignore
        }
      }
    }
  }, []);

  const triggerHaptic = (style: 'light' | 'medium' | 'heavy' = 'light') => {
    try {
      const tg = (window as unknown as { Telegram?: { WebApp?: { HapticFeedback?: { impactOccurred: (s: string) => void } } } })?.Telegram?.WebApp;
      tg?.HapticFeedback?.impactOccurred(style);
    } catch {
      // ignore
    }
  };

  return (
    <TelegramContext.Provider value={{ isTWA, user, triggerHaptic }}>
      {children}
    </TelegramContext.Provider>
  );
};

export const useTelegram = () => useContext(TelegramContext);
