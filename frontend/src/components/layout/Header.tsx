'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname } from 'next/navigation';
import { api } from '@/lib/api';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { BottomNav } from '@/components/layout/BottomNav';
import { Badge } from '@/components/ui/Badge';
import {
  Menu,
  X,
  HelpCircle,
  Ticket,
  BookOpen,
  TrendingUp,
  Settings,
  CheckCircle2,
  AlertCircle,
  Globe,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  Send,
} from 'lucide-react';

export const Header: React.FC = () => {
  const pathname = usePathname();
  const { locale, toggleLocale, setLocale, t } = useTranslation();
  const { user, isAdmin, triggerHaptic } = useTelegram();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');

  // Check backend health
  useEffect(() => {
    let isMounted = true;
    const check = async () => {
      try {
        await api.checkHealth();
        if (isMounted) setApiStatus('connected');
      } catch {
        if (isMounted) setApiStatus('disconnected');
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (isMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMenuOpen]);

  const navLinks = [
    { href: '/', label: t.navSupport, icon: HelpCircle, desc: locale === 'fr' ? 'Recherche & FAQ interactive' : 'Interactive Search & FAQ' },
    { href: '/tickets', label: t.navTickets, icon: Ticket, desc: locale === 'fr' ? 'Suivi de vos demandes' : 'Track your requests' },
    {
      href: '/knowledge',
      label: isAdmin ? t.navKnowledge : (locale === 'fr' ? 'FAQ' : 'FAQ'),
      icon: BookOpen,
      desc: isAdmin
        ? (locale === 'fr' ? 'Base de connaissances & modération' : 'Knowledge Base & Moderation')
        : (locale === 'fr' ? 'Top 10 questions fréquentes' : 'Top 10 common questions'),
    },
    { href: '/crypto', label: t.navCrypto, icon: TrendingUp, desc: locale === 'fr' ? 'Cours des actifs en direct' : 'Live asset rates' },
    ...(isAdmin ? [{ href: '/settings', label: t.navSettings, icon: Settings, desc: locale === 'fr' ? 'Modération & Configuration' : 'Moderation & Setup' }] : []),
  ];

  const handleOpenMenu = () => {
    triggerHaptic('light');
    setIsMenuOpen(true);
  };

  const handleCloseMenu = () => {
    triggerHaptic('light');
    setIsMenuOpen(false);
  };

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-white/[0.08] bg-black/80 backdrop-blur-2xl transition-colors">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-3.5 py-2.5 sm:px-6">
          {/* Logo: Image icon part only + "Support" text */}
          <Link
            href="/"
            className="flex items-center gap-2.5 group py-0.5 focus:outline-none"
            onClick={() => setIsMenuOpen(false)}
          >
            <div className="flex items-center gap-2">
              <Image
                src="/stack-icon-white.png"
                alt="Stack Wallet"
                width={24}
                height={24}
                className="h-6 w-6 object-contain drop-shadow-md transition-transform group-hover:scale-105"
                priority
              />
              <span className="text-sm sm:text-base font-bold tracking-tight text-white">
                Support
              </span>
            </div>
          </Link>

          {/* Action Controls: Compact Language Switcher & Mobile Menu Button */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* Quick Language Toggle */}
            <button
              onClick={toggleLocale}
              className="flex items-center gap-1.5 rounded-xl border border-white/[0.1] bg-white/[0.04] px-2.5 py-1.5 text-xs font-semibold text-white hover:border-white/30 hover:bg-white/[0.08] transition-all cursor-pointer shadow-sm active:scale-95"
              title="Changer de langue / Switch language"
              aria-label="Toggle language"
            >
              <Globe className="h-3.5 w-3.5 text-white" />
              <span className="uppercase tracking-wider text-[11px] font-bold text-white">
                {locale.toUpperCase()}
              </span>
            </button>

            {/* Menu Button */}
            <button
              onClick={handleOpenMenu}
              className="flex items-center gap-1.5 rounded-xl border border-white/[0.12] bg-white/[0.05] hover:bg-white/[0.1] hover:border-white/30 px-3 py-1.5 text-xs font-semibold text-white transition-all cursor-pointer active:scale-95 shadow-sm"
              aria-label="Ouvrir le menu"
            >
              <Menu className="h-4 w-4 text-white" />
              <span>Menu</span>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile-First Bottom Navigation Bar */}
      <BottomNav onOpenMenu={handleOpenMenu} />

      {/* Slide-over Mobile Drawer Menu */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-md transition-opacity duration-300"
            onClick={handleCloseMenu}
            aria-hidden="true"
          />

          {/* Drawer Container */}
          <aside
            role="dialog"
            aria-modal="true"
            className="relative z-10 w-full max-w-sm h-full bg-black/95 backdrop-blur-2xl border-l border-white/[0.12] flex flex-col justify-between shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-200"
          >
            {/* Drawer Header */}
            <div>
              <div className="flex items-center justify-between p-4 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <Image
                    src="/stack-icon-white.png"
                    alt="Stack Wallet"
                    width={20}
                    height={20}
                    className="h-5 w-5 object-contain"
                  />
                  <span className="text-sm font-bold tracking-tight text-white">
                    Support
                  </span>
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-white bg-white/10 border border-white/20 px-1.5 py-0.5 rounded">
                    Menu
                  </span>
                </div>
                <button
                  onClick={handleCloseMenu}
                  className="rounded-xl p-2 text-neutral-400 hover:text-white hover:bg-white/[0.08] transition-colors"
                  aria-label="Fermer le menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* User Profile Banner (if in Telegram) */}
              {user && (
                <div className="mx-4 mt-4 p-3 rounded-xl bg-white/[0.04] border border-white/[0.1] flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-white/10 border border-white/15 flex items-center justify-center font-bold text-white text-xs uppercase">
                      {(user.first_name || user.username || 'TG').slice(0, 2)}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-white">
                          {user.first_name || user.username}
                        </span>
                        {isAdmin && (
                          <span className="text-[9px] font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1 py-0.2 rounded">
                            Admin
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-neutral-400">Telegram WebApp</div>
                    </div>
                  </div>
                  <span className="h-2 w-2 rounded-full bg-white shadow-[0_0_6px_rgba(255,255,255,0.8)] animate-pulse" />
                </div>
              )}

              {/* Navigation Items */}
              <nav className="p-4 space-y-1.5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400 px-3 py-1">
                  {locale === 'fr' ? 'Navigation' : 'Menu Navigation'}
                </div>

                {navLinks.map((link) => {
                  const Icon = link.icon;
                  const isActive = pathname === link.href;

                  return (
                    <Link
                      key={link.href}
                      href={link.href}
                      onClick={handleCloseMenu}
                      className={`flex items-center justify-between p-3 rounded-xl transition-all ${
                        isActive
                          ? 'bg-white text-black font-semibold shadow-lg shadow-white/10'
                          : 'text-neutral-300 hover:bg-white/[0.06] hover:text-white'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-9 w-9 items-center justify-center rounded-lg ${
                            isActive
                              ? 'bg-black/10 text-black'
                              : 'bg-white/[0.04] text-neutral-300 border border-white/[0.08]'
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <div>
                          <div className="text-xs sm:text-sm font-medium leading-tight">
                            {link.label}
                          </div>
                          <div
                            className={`text-[10px] mt-0.5 ${
                              isActive ? 'text-neutral-700' : 'text-neutral-400'
                            }`}
                          >
                            {link.desc}
                          </div>
                        </div>
                      </div>
                      <ChevronRight
                        className={`h-4 w-4 shrink-0 ${
                          isActive ? 'text-black' : 'text-neutral-400'
                        }`}
                      />
                    </Link>
                  );
                })}
              </nav>

              {/* Quick Links Section */}
              <div className="px-4 py-2 border-t border-white/[0.08]">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400 px-3 py-1">
                  {locale === 'fr' ? 'Communauté & Liens' : 'Community & Links'}
                </div>
                <div className="space-y-1 mt-1">
                  <a
                    href="https://t.me/STACK_WALLET_BOT"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-2.5 rounded-lg text-xs text-neutral-300 hover:bg-white/[0.06] hover:text-white transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Send className="h-3.5 w-3.5 text-white" />
                      <span>{locale === 'fr' ? 'Bot Telegram Officiel' : 'Official Telegram Bot'}</span>
                    </span>
                    <ExternalLink className="h-3 w-3 text-neutral-400" />
                  </a>

                  <a
                    href="https://stackwallet.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-2.5 rounded-lg text-xs text-neutral-300 hover:bg-white/[0.06] hover:text-white transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <ShieldCheck className="h-3.5 w-3.5 text-white" />
                      <span>stackwallet.com</span>
                    </span>
                    <ExternalLink className="h-3 w-3 text-neutral-400" />
                  </a>
                </div>
              </div>
            </div>

            {/* Drawer Footer: Language switch & Status */}
            <div className="p-4 border-t border-white/[0.08] bg-black/80 space-y-3">
              {/* Language Selector */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-neutral-400">
                  {locale === 'fr' ? 'Langue d’affichage' : 'Display Language'}
                </span>
                <div className="flex rounded-lg bg-white/[0.04] p-0.5 border border-white/[0.08]">
                  <button
                    onClick={() => setLocale('fr')}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                      locale === 'fr'
                        ? 'bg-white text-black shadow-sm'
                        : 'text-neutral-400 hover:text-white'
                    }`}
                  >
                    FR
                  </button>
                  <button
                    onClick={() => setLocale('en')}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all ${
                      locale === 'en'
                        ? 'bg-white text-black shadow-sm'
                        : 'text-neutral-400 hover:text-white'
                    }`}
                  >
                    EN
                  </button>
                </div>
              </div>

              {/* Server Status */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-slate-400">
                  {locale === 'fr' ? 'État des services' : 'System status'}
                </span>
                {apiStatus === 'connected' ? (
                  <Badge variant="success" size="sm">
                    <CheckCircle2 className="h-3 w-3" />
                    <span>{t.apiConnected}</span>
                  </Badge>
                ) : apiStatus === 'disconnected' ? (
                  <Badge variant="error" size="sm">
                    <AlertCircle className="h-3 w-3" />
                    <span>{t.apiOffline}</span>
                  </Badge>
                ) : (
                  <Badge variant="neutral" size="sm">
                    <span className="h-1.5 w-1.5 rounded-full bg-slate-400 animate-pulse" />
                    <span>{t.apiChecking}</span>
                  </Badge>
                )}
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
};
