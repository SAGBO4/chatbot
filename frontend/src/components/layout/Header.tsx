'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { usePathname, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
import { BottomNav } from '@/components/layout/BottomNav';
import {
  Menu,
  X,
  HelpCircle,
  Ticket,
  BookOpen,
  TrendingUp,
  Settings,
  Globe,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  Send,
  Copy,
  Command,
  Check,
} from 'lucide-react';

export const Header: React.FC = () => {
  const pathname = usePathname();
  const router = useRouter();
  const { locale, toggleLocale, setLocale, t } = useTranslation();
  const { user, isAdmin, triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [copiedId, setCopiedId] = useState(false);

  // Check backend health & measure network latency
  const checkHealth = useCallback(async () => {
    const t0 = performance.now();
    try {
      await api.checkHealth();
      const elapsed = Math.round(performance.now() - t0);
      setLatencyMs(elapsed > 0 ? elapsed : 12);
      setApiStatus('connected');
    } catch {
      setLatencyMs(null);
      setApiStatus('disconnected');
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      checkHealth();
    }, 0);
    const interval = setInterval(checkHealth, 30000);
    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [checkHealth]);

  // Global ⌘K / Ctrl+K shortcut listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const searchInput = document.querySelector('input[type="text"]') as HTMLInputElement | null;
        if (searchInput) {
          searchInput.focus();
          searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
          router.push('/');
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [router]);

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
    { href: '/', label: t.navSupport, icon: HelpCircle },
    { href: '/tickets', label: t.navTickets, icon: Ticket },
    { href: '/knowledge', label: t.navKnowledge, icon: BookOpen },
    { href: '/crypto', label: t.navCrypto, icon: TrendingUp },
    ...(isAdmin ? [{ href: '/settings', label: t.navSettings, icon: Settings }] : []),
  ];

  const handleOpenMenu = () => {
    triggerHaptic('light');
    setIsMenuOpen(true);
  };

  const handleCloseMenu = () => {
    triggerHaptic('light');
    setIsMenuOpen(false);
  };

  const handleToggleLang = () => {
    triggerHaptic('light');
    const newLocale = locale === 'fr' ? 'en' : 'fr';
    toggleLocale();
    toast({
      title: newLocale === 'fr' ? 'Langue modifiée' : 'Language changed',
      description: newLocale === 'fr' ? 'Interface basculée en Français' : 'Interface switched to English',
      variant: 'default',
    });
  };

  const handleCopyUserId = (idToCopy: string | number) => {
    triggerHaptic('light');
    navigator.clipboard?.writeText(String(idToCopy));
    setCopiedId(true);
    toast({
      title: locale === 'fr' ? 'Identifiant copié' : 'User ID copied',
      description: `ID: ${idToCopy}`,
      variant: 'success',
    });
    setTimeout(() => setCopiedId(false), 2000);
  };

  // Compute breadcrumb trail
  const currentSectionName =
    pathname === '/tickets'
      ? t.navTickets
      : pathname === '/knowledge'
      ? t.navKnowledge
      : pathname === '/crypto'
      ? t.navCrypto
      : pathname === '/settings'
      ? t.navSettings
      : null;

  return (
    <>
      <header className="sticky top-0 z-40 w-full border-b border-white/[0.08] bg-[#09090b]/90 backdrop-blur-2xl transition-colors">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
          {/* Logo & Workspace Breadcrumb */}
          <div className="flex items-center gap-5 sm:gap-6">
            <Link
              href="/"
              className="flex items-center gap-2.5 group py-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-zinc-400 rounded-lg"
              onClick={() => setIsMenuOpen(false)}
            >
              <Image
                src="/stack-logo-white.png"
                alt="Stack Wallet"
                width={128}
                height={27}
                className="h-6 w-auto object-contain transition-opacity group-hover:opacity-85"
                priority
              />
              <span className="text-[10px] font-semibold text-zinc-300 bg-white/[0.08] border border-white/[0.15] px-1.5 py-0.5 rounded tracking-wider uppercase">
                Support
              </span>
            </Link>

            {/* Breadcrumb indicator (Desktop) */}
            {currentSectionName && (
              <div className="hidden lg:flex items-center gap-2 text-xs text-zinc-400 border-l border-white/[0.08] pl-5">
                <ChevronRight className="h-3.5 w-3.5 text-zinc-600" />
                <span className="font-medium text-zinc-200">{currentSectionName}</span>
              </div>
            )}

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1.5 ml-2">
              {navLinks.map((link) => {
                const isActive = pathname === link.href;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-white/[0.1] text-white border border-white/20 font-semibold shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.04]'
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Action Controls */}
          <div className="flex items-center gap-2 sm:gap-3">
            {/* ⌘K Command Shortcut pill */}
            <button
              onClick={() => {
                const searchInput = document.querySelector('input[type="text"]') as HTMLInputElement | null;
                if (searchInput) {
                  searchInput.focus();
                  searchInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
                } else {
                  router.push('/');
                }
              }}
              className="hidden lg:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 border border-white/[0.08] hover:border-white/[0.18] text-[11px] text-zinc-400 hover:text-zinc-200 transition-all cursor-pointer shadow-sm"
              title="Rechercher (⌘K / Ctrl+K)"
            >
              <Command className="h-3 w-3 text-zinc-400" />
              <span>{locale === 'fr' ? 'Rechercher' : 'Search'}</span>
              <kbd className="ml-1 px-1 py-0.5 text-[10px] font-mono bg-zinc-800 rounded border border-white/[0.1] text-zinc-300">
                ⌘K
              </kbd>
            </button>

            {/* Health / Latency Status Badge */}
            <button
              onClick={checkHealth}
              className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-full bg-zinc-900 border border-white/[0.08] text-[11px] text-zinc-300 font-medium hover:border-white/[0.18] transition-all cursor-pointer"
              title={
                apiStatus === 'connected'
                  ? `Nœud connecté • Latence: ${latencyMs ?? 12}ms`
                  : 'Vérifier la connectivité'
              }
            >
              <span className="relative flex h-2 w-2">
                <span
                  className={`inline-flex rounded-full h-2 w-2 ${
                    apiStatus === 'connected'
                      ? 'bg-zinc-400'
                      : apiStatus === 'disconnected'
                      ? 'bg-rose-400'
                      : 'bg-zinc-600'
                  }`}
                />
              </span>
              <span className="hidden sm:inline">
                {apiStatus === 'connected'
                  ? `${latencyMs ? `${latencyMs} ms • ` : ''}${t.apiConnected}`
                  : apiStatus === 'disconnected'
                  ? t.apiOffline
                  : t.apiChecking}
              </span>
            </button>

            {/* User Profile Pill (if user present) */}
            {user && (
              <button
                onClick={() => handleCopyUserId(user.id)}
                className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-zinc-900 border border-white/[0.08] hover:border-white/[0.18] text-xs text-zinc-300 hover:text-zinc-100 transition-all cursor-pointer group"
                title="Cliquer pour copier votre identifiant Telegram"
              >
                <div className="h-5 w-5 rounded-full bg-zinc-800 flex items-center justify-center font-bold text-[10px] text-zinc-200 uppercase">
                  {(user.first_name || user.username || 'U').slice(0, 1)}
                </div>
                <span className="font-medium text-zinc-200 max-w-[90px] truncate">
                  {user.first_name || user.username}
                </span>
                {copiedId ? (
                  <Check className="h-3 w-3 text-zinc-200 shrink-0" />
                ) : (
                  <Copy className="h-3 w-3 text-zinc-500 group-hover:text-zinc-300 shrink-0" />
                )}
              </button>
            )}

            {/* Admin Badge */}
            {isAdmin && (
              <span className="hidden sm:inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-white/10 border border-white/20 text-[10px] font-semibold text-zinc-200 tracking-wider uppercase">
                Admin
              </span>
            )}

            {/* Language Switcher */}
            <button
              onClick={handleToggleLang}
              className="flex items-center gap-1.5 rounded-lg border border-white/[0.1] bg-zinc-900 px-2.5 py-1.5 text-xs font-medium text-zinc-200 hover:border-white/[0.25] hover:bg-zinc-800 transition-all cursor-pointer shadow-sm active:scale-95"
              title="Changer de langue / Switch language"
              aria-label="Toggle language"
            >
              <Globe className="h-3.5 w-3.5 text-zinc-400" />
              <span className="uppercase tracking-wider text-[11px] font-bold text-zinc-200">
                {locale.toUpperCase()}
              </span>
            </button>

            {/* Mobile Menu Button */}
            <button
              onClick={handleOpenMenu}
              className="md:hidden flex items-center gap-1.5 rounded-lg border border-white/[0.12] bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-xs font-semibold text-zinc-100 transition-all cursor-pointer active:scale-95 shadow-sm"
              aria-label={t.openMenu}
            >
              <Menu className="h-4 w-4 text-zinc-200" />
              <span className="sr-only">Menu</span>
            </button>
          </div>
        </div>
      </header>

      {/* Mobile-Only Bottom Navigation Bar */}
      <BottomNav onOpenMenu={handleOpenMenu} />

      {/* Slide-over Mobile Drawer Menu */}
      {isMenuOpen && (
        <div className="fixed inset-0 z-50 flex justify-end md:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity duration-300"
            onClick={handleCloseMenu}
            aria-hidden="true"
          />

          {/* Drawer Container */}
          <aside
            role="dialog"
            aria-modal="true"
            className="relative z-10 w-full max-w-sm h-full bg-[#0d0d10] border-l border-white/[0.1] flex flex-col justify-between shadow-2xl overflow-y-auto animate-in slide-in-from-right duration-200"
          >
            {/* Drawer Header */}
            <div>
              <div className="flex items-center justify-between p-4 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <Image
                    src="/stack-icon-white.png"
                    alt="Stack Wallet"
                    width={22}
                    height={22}
                    className="h-5 w-5 object-contain"
                  />
                  <span className="text-sm font-semibold tracking-tight text-zinc-100">
                    Stack Wallet Support
                  </span>
                </div>
                <button
                  onClick={handleCloseMenu}
                  className="rounded-lg p-1.5 text-zinc-400 hover:text-white hover:bg-zinc-800 transition-colors cursor-pointer"
                  aria-label={t.closeMenu}
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* User Profile Banner (if in Telegram) */}
              {user && (
                <div className="mx-4 mt-4 p-3 rounded-xl bg-zinc-900 border border-white/[0.08] flex items-center justify-between">
                  <div className="flex items-center gap-2.5">
                    <div className="h-8 w-8 rounded-lg bg-zinc-800 border border-white/[0.1] flex items-center justify-center font-bold text-zinc-200 text-xs uppercase">
                      {(user.first_name || user.username || 'TG').slice(0, 2)}
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-zinc-100">
                          {user.first_name || user.username}
                        </span>
                        {isAdmin && (
                          <span className="text-[9px] font-bold uppercase tracking-wider bg-white/15 text-zinc-200 border border-white/20 px-1.5 py-0.5 rounded">
                            Admin
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-zinc-400">ID: {user.id}</div>
                    </div>
                  </div>
                  <button
                    onClick={() => handleCopyUserId(user.id)}
                    className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs transition-colors"
                    title="Copier mon ID"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}

              {/* Navigation Items */}
              <nav className="p-4 space-y-1.5">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 px-3 py-1">
                  {locale === 'fr' ? 'Navigation' : 'Navigation'}
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
                          ? 'bg-zinc-100 text-zinc-950 font-semibold shadow-sm'
                          : 'text-zinc-300 hover:bg-zinc-850 hover:text-zinc-100'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                            isActive
                              ? 'bg-zinc-900/15 text-zinc-950'
                              : 'bg-zinc-900 text-zinc-300 border border-white/[0.08]'
                          }`}
                        >
                          <Icon className="h-4 w-4" />
                        </div>
                        <span className="text-xs sm:text-sm font-medium leading-tight">
                          {link.label}
                        </span>
                      </div>
                      <ChevronRight
                        className={`h-4 w-4 shrink-0 ${
                          isActive ? 'text-zinc-950' : 'text-zinc-500'
                        }`}
                      />
                    </Link>
                  );
                })}
              </nav>

              {/* Quick Links Section */}
              <div className="px-4 py-2 border-t border-white/[0.08]">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 px-3 py-1">
                  {locale === 'fr' ? 'Communauté & Ressources' : 'Community & Resources'}
                </div>
                <div className="space-y-1 mt-1">
                  <a
                    href="https://t.me/STACK_WALLET_BOT"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-2.5 rounded-lg text-xs text-zinc-300 hover:bg-zinc-850 hover:text-white transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Send className="h-3.5 w-3.5 text-zinc-300" />
                      <span>{locale === 'fr' ? 'Support Telegram Officiel' : 'Official Telegram Support'}</span>
                    </span>
                    <ExternalLink className="h-3 w-3 text-zinc-500" />
                  </a>

                  <a
                    href="https://stackwallet.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-2.5 rounded-lg text-xs text-zinc-300 hover:bg-zinc-850 hover:text-white transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <ShieldCheck className="h-3.5 w-3.5 text-zinc-300" />
                      <span>stackwallet.com</span>
                    </span>
                    <ExternalLink className="h-3 w-3 text-zinc-500" />
                  </a>
                </div>
              </div>
            </div>

            {/* Drawer Footer: Language switch & Status */}
            <div className="p-4 border-t border-white/[0.08] bg-zinc-950 space-y-3">
              {/* Language Selector */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-zinc-400">
                  {locale === 'fr' ? 'Langue d’affichage' : 'Display Language'}
                </span>
                <div className="flex rounded-lg bg-zinc-900 p-0.5 border border-white/[0.08]">
                  <button
                    onClick={() => {
                      setLocale('fr');
                      toast({
                        title: 'Langue modifiée',
                        description: 'Interface basculée en Français',
                        variant: 'default',
                      });
                    }}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                      locale === 'fr'
                        ? 'bg-zinc-100 text-zinc-950 shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    FR
                  </button>
                  <button
                    onClick={() => {
                      setLocale('en');
                      toast({
                        title: 'Language changed',
                        description: 'Interface switched to English',
                        variant: 'default',
                      });
                    }}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-all cursor-pointer ${
                      locale === 'en'
                        ? 'bg-zinc-100 text-zinc-950 shadow-sm'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    EN
                  </button>
                </div>
              </div>

              {/* Server Status */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-[11px] text-zinc-400">
                  {locale === 'fr' ? 'État des services' : 'System status'}
                </span>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-white/[0.06] border border-white/[0.1] text-[11px] font-medium text-zinc-300">
                  <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" />
                  <span>{apiStatus === 'connected' ? t.apiConnected : t.apiOffline}</span>
                </span>
              </div>
            </div>
          </aside>
        </div>
      )}
    </>
  );
};
