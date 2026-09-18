'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import {
  HelpCircle,
  Ticket,
  BookOpen,
  TrendingUp,
  Menu,
} from 'lucide-react';

interface BottomNavProps {
  onOpenMenu: () => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({ onOpenMenu }) => {
  const pathname = usePathname();
  const { t } = useTranslation();
  const { triggerHaptic } = useTelegram();

  const tabs = [
    { href: '/', label: t.navSupport, icon: HelpCircle },
    { href: '/tickets', label: t.navTickets, icon: Ticket },
    { href: '/knowledge', label: t.navKnowledge, icon: BookOpen },
    { href: '/crypto', label: t.navCrypto, icon: TrendingUp },
  ];

  return (
    <nav
      aria-label="Navigation mobile"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-white/[0.08] bg-black/85 backdrop-blur-2xl transition-all"
      style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 0.5rem)' }}
    >
      <div className="mx-auto flex max-w-lg items-center justify-around px-2 pt-1.5">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = pathname === tab.href;

          return (
            <Link
              key={tab.href}
              href={tab.href}
              onClick={() => triggerHaptic('light')}
              className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all duration-150 min-w-[56px] ${
                isActive
                  ? 'text-white font-semibold'
                  : 'text-neutral-400 hover:text-white active:scale-95'
              }`}
            >
              <div
                className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors ${
                  isActive ? 'bg-white/15 text-white border border-white/20 shadow-sm shadow-white/5' : ''
                }`}
              >
                <Icon className="h-4 w-4" />
              </div>
              <span className="text-[10px] mt-0.5 tracking-tight truncate max-w-[64px] text-center">
                {tab.label}
              </span>
            </Link>
          );
        })}

        {/* Menu Tab Button */}
        <button
          type="button"
          onClick={() => {
            triggerHaptic('medium');
            onOpenMenu();
          }}
          className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all duration-150 min-w-[56px] ${
            pathname === '/settings'
              ? 'text-white font-semibold'
              : 'text-neutral-400 hover:text-white active:scale-95'
          }`}
          aria-label="Ouvrir le menu complet"
        >
          <div
            className={`flex h-7 w-7 items-center justify-center rounded-lg transition-colors ${
              pathname === '/settings' ? 'bg-white/15 text-white border border-white/20' : ''
            }`}
          >
            <Menu className="h-4 w-4" />
          </div>
          <span className="text-[10px] mt-0.5 tracking-tight truncate max-w-[64px] text-center">
            Menu
          </span>
        </button>
      </div>
    </nav>
  );
};
