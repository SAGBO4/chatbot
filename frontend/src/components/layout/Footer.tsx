'use client';

import React from 'react';
import Link from 'next/link';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { ExternalLink, ShieldCheck, BookOpen, Coins } from 'lucide-react';

export const Footer: React.FC = () => {
  const { t } = useTranslation();

  return (
    <footer className="w-full border-t border-white/[0.08] bg-black/60 backdrop-blur-xl pt-6 pb-24 sm:pb-8 text-xs text-neutral-400">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
        <div className="flex items-center gap-2 text-center sm:text-left">
          <span className="font-bold text-white tracking-wide text-xs">
            Stack <span className="text-neutral-400">Support</span>
          </span>
          <span className="text-neutral-700">•</span>
          <span className="text-neutral-500 text-[11px]">{t.poweredBy}</span>
        </div>

        <div className="flex flex-wrap items-center gap-5">
          <Link href="/knowledge" className="hover:text-white transition-colors flex items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5" />
            <span>{t.navKnowledge}</span>
          </Link>
          <Link href="/crypto" className="hover:text-white transition-colors flex items-center gap-1.5">
            <Coins className="h-3.5 w-3.5" />
            <span>{t.navCrypto}</span>
          </Link>
          <a
            href="https://stackwallet.com"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-white transition-colors"
          >
            <span>stackwallet.com</span>
            <ExternalLink className="h-3 w-3" />
          </a>
          <a
            href="https://github.com/cypherstack/stack_wallet"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 hover:text-white transition-colors"
          >
            <span>GitHub</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        <div className="flex items-center gap-1.5 text-neutral-500">
          <ShieldCheck className="h-3.5 w-3.5 text-white" />
          <span>Open-Source & Privacy-Preserving</span>
        </div>
      </div>
    </footer>
  );
};
