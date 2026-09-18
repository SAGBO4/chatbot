'use client';

import React, { createContext, useContext, useState } from 'react';
import { Locale, translations } from './translations';

interface LanguageContextType {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  t: (typeof translations)['fr'];
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [locale, setLocaleState] = useState<Locale>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('app_locale') as Locale;
        if (saved === 'fr' || saved === 'en') return saved;
      } catch {
        // ignore
      }
    }
    return 'fr';
  });

  const setLocale = (newLocale: Locale) => {
    setLocaleState(newLocale);
    try {
      localStorage.setItem('app_locale', newLocale);
    } catch {
      // ignore
    }
  };

  const toggleLocale = () => {
    const next = locale === 'fr' ? 'en' : 'fr';
    setLocale(next);
  };

  const t = translations[locale] || translations.fr;

  return (
    <LanguageContext.Provider value={{ locale, setLocale, toggleLocale, t }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useTranslation = () => {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useTranslation must be used within a LanguageProvider');
  }
  return context;
};
