'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

import { api, setTelegramInitData } from '@/lib/api';

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
  isAdmin: boolean;
  isLoadingAdmin: boolean;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

const TelegramContext = createContext<TelegramContextType>({
  isTWA: false,
  user: null,
  isAdmin: false,
  isLoadingAdmin: false,
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
      const tg = (window as unknown as {
        Telegram?: { WebApp?: { initData?: string; initDataUnsafe?: { user?: TelegramUser } } };
      })?.Telegram?.WebApp;

      // Captured synchronously here (not in a useEffect) so it is set
      // before any effect - including the admin-role check right below -
      // ever calls the API. Not a React state update, just a module-level
      // value read by api.ts's getHeaders() on every request.
      setTelegramInitData(tg?.initData || null);

      if (tg?.initDataUnsafe?.user) {
        return tg.initDataUnsafe.user;
      }
      // Dev-only test shortcut so the Mini App can be exercised outside of
      // Telegram during local development. Never active in a production
      // build: without this guard, anyone could open the deployed app with
      // ?user_id=<victim> and have the UI believe it is that user (see the
      // Telegram identity spoofing finding).
      if (process.env.NODE_ENV !== 'production') {
        try {
          const params = new URLSearchParams(window.location.search);
          const devUserId = params.get('user_id');
          if (devUserId && !isNaN(Number(devUserId))) {
            return { id: Number(devUserId), username: 'DevTester', first_name: 'Dev' };
          }
        } catch {
          // ignore
        }
      }
    }
    return null;
  });

  const [isAdmin, setIsAdmin] = useState<boolean>(false);
  const [isLoadingAdmin, setIsLoadingAdmin] = useState<boolean>(true);

  useEffect(() => {
    let ignore = false;

    const checkAdminRole = async () => {
      // Dev-only query param shortcut (see the user-id shortcut above) -
      // never active in a production build, otherwise ?admin=1 would let
      // any visitor grant themselves the admin UI without ever being
      // checked against the real whitelist.
      if (process.env.NODE_ENV !== 'production' && typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        if (params.get('admin') === '1' || params.get('admin') === 'true') {
          if (!ignore) {
            setIsAdmin(true);
            setIsLoadingAdmin(false);
          }
          return;
        }
      }

      if (!user?.id) {
        if (!ignore) {
          setIsAdmin(false);
          setIsLoadingAdmin(false);
        }
        return;
      }

      try {
        const check = await api.checkWhitelist(user.id);
        if (!ignore) {
          setIsAdmin(Boolean(check?.is_whitelisted));
        }
      } catch {
        if (!ignore) {
          setIsAdmin(false);
        }
      } finally {
        if (!ignore) {
          setIsLoadingAdmin(false);
        }
      }
    };

    checkAdminRole();
    return () => {
      ignore = true;
    };
  }, [user]);

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
    <TelegramContext.Provider value={{ isTWA, user, isAdmin, isLoadingAdmin, triggerHaptic }}>
      {children}
    </TelegramContext.Provider>
  );
};

export const useTelegram = () => useContext(TelegramContext);
