'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { QueryResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { AnswerCard } from '@/components/support/AnswerCard';
import { TicketForm } from '@/components/tickets/TicketForm';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import {
  Search,
  BookOpen,
  Ticket,
  TrendingUp,
  Headphones,
  KeyRound,
  Server,
  ArrowLeftRight,
  ShieldCheck,
  ArrowRight,
  X,
} from 'lucide-react';

const SUGGESTIONS_FR = [
  { label: 'Restauration Seed', icon: KeyRound, query: 'Comment restaurer mon portefeuille avec la phrase de récupération ?' },
  { label: 'Gestion des Nœuds', icon: Server, query: 'Comment se connecter à un nœud distant ou local ?' },
  { label: 'Swaps & Échanges', icon: ArrowLeftRight, query: 'Comment fonctionne l’échange intégré sans tiers ?' },
  { label: 'Sécurité & Sauvegarde', icon: ShieldCheck, query: 'Comment sauvegarder mes clés en toute sécurité ?' },
];

const SUGGESTIONS_EN = [
  { label: 'Seed Recovery', icon: KeyRound, query: 'How do I restore my wallet using my recovery seed phrase?' },
  { label: 'Node Setup', icon: Server, query: 'How to configure custom remote and local nodes?' },
  { label: 'In-app Swaps', icon: ArrowLeftRight, query: 'How does the built-in non-custodial exchange work?' },
  { label: 'Security & Backup', icon: ShieldCheck, query: 'How to securely backup wallet data and keys?' },
];

export default function HomePage() {
  const { locale, t } = useTranslation();
  const { triggerHaptic } = useTelegram();
  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEscalation, setShowEscalation] = useState(false);

  const suggestions = locale === 'fr' ? SUGGESTIONS_FR : SUGGESTIONS_EN;

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    setError(null);
    setShowEscalation(false);
    triggerHaptic('light');

    try {
      const res = await api.querySupport({ query: searchQuery.trim() });
      setResult(res);
      if (!res.found || res.confidence < 0.35) {
        setShowEscalation(true);
      }
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errSearch;
      setError(msg);
      setResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSearch(query);
  };

  const handleSuggestedClick = (suggestedQuery: string) => {
    setQuery(suggestedQuery);
    handleSearch(suggestedQuery);
  };

  return (
    <div className="mx-auto max-w-5xl px-3.5 py-6 sm:px-6 lg:py-12">
      {/* Hero Header */}
      <div className="text-center mb-8 sm:mb-10">
        <h1 className="text-2xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl max-w-2xl mx-auto leading-tight">
          {t.heroTitle}
        </h1>
        <p className="mt-2.5 max-w-xl mx-auto text-xs sm:text-sm text-slate-400 leading-relaxed">
          {t.heroSubtitle}
        </p>

        {/* Glassmorphic Search Input */}
        <div className="mt-6 max-w-xl mx-auto">
          <form onSubmit={onSubmit} className="relative flex items-center">
            <div className="relative w-full flex items-center rounded-2xl bg-white/[0.04] backdrop-blur-2xl border border-white/[0.12] shadow-2xl shadow-black/60 focus-within:border-white/40 focus-within:ring-2 focus-within:ring-white/10 transition-all">
              <Search className="absolute left-3.5 h-4 w-4 text-neutral-400 pointer-events-none" />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t.searchPlaceholder}
                className="w-full bg-transparent pl-10 pr-28 py-3 text-sm text-white placeholder-neutral-500 focus:outline-none"
              />
              {query && (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-24 p-1.5 text-neutral-400 hover:text-white transition-colors cursor-pointer"
                  title="Effacer"
                  aria-label={t.clearSearch}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
              <div className="absolute right-1.5">
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isLoading}
                  className="rounded-xl px-3.5 py-1.5 text-xs shadow-md shadow-white/10"
                >
                  {t.searchButton}
                </Button>
              </div>
            </div>
          </form>

          {/* Quick Filter Suggestion Chips */}
          <div className="mt-3.5 flex flex-wrap items-center justify-center gap-1.5 sm:gap-2">
            <span className="text-[11px] text-neutral-400 font-medium mr-0.5">{t.popularQueries}</span>
            {suggestions.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => handleSuggestedClick(item.query)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.03] backdrop-blur-md px-2.5 py-1 text-[11px] sm:text-xs text-neutral-300 transition-all hover:border-white/30 hover:text-white hover:bg-white/[0.08] active:scale-95 cursor-pointer"
                >
                  <Icon className="h-3 w-3 text-neutral-300" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="max-w-2xl mx-auto mb-6">
          <Alert type="error" title={t.searchErrorTitle}>
            {error}
          </Alert>
        </div>
      )}

      {/* Search Result Card */}
      {result && (
        <div className="max-w-2xl mx-auto mb-8">
          <AnswerCard
            result={result}
            onEscalate={() => setShowEscalation(true)}
          />
        </div>
      )}

      {/* Escalation Form Card */}
      {showEscalation && (
        <div className="max-w-2xl mx-auto mb-10">
          <TicketForm
            initialQuestion={query}
            initialAutomatedAnswer={result?.answer}
            onCancel={() => setShowEscalation(false)}
          />
        </div>
      )}

      {/* 4 Quick-Action Help Desk Cards - Mobile First Monochrome Glass Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-6">
        <Link href="/knowledge" className="group block">
          <Card elevated hoverable className="p-3.5 sm:p-5 h-full transition-all">
            <div className="flex items-center gap-3.5 sm:flex-col sm:items-start sm:gap-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] sm:mb-2.5 group-hover:bg-white group-hover:text-black transition-all">
                <BookOpen className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-xs sm:text-sm font-semibold text-white transition-colors truncate">
                  {t.navKnowledge}
                </h3>
                <p className="mt-0.5 sm:mt-1 text-[11px] sm:text-xs text-neutral-400 leading-relaxed line-clamp-2">
                  {locale === 'fr'
                    ? 'Guides officiels, configurations de nœuds et FAQ.'
                    : 'Official guides, node setups, and FAQs.'}
                </p>
              </div>
              <div className="sm:mt-3 flex items-center text-[11px] font-medium text-neutral-400 group-hover:text-white shrink-0 group-hover:translate-x-0.5 transition-all">
                <span className="hidden sm:inline mr-1">{locale === 'fr' ? 'Consulter' : 'Browse'}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </div>
          </Card>
        </Link>

        <Link href="/tickets" className="group block">
          <Card elevated hoverable className="p-3.5 sm:p-5 h-full transition-all">
            <div className="flex items-center gap-3.5 sm:flex-col sm:items-start sm:gap-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] sm:mb-2.5 group-hover:bg-white group-hover:text-black transition-all">
                <Ticket className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-xs sm:text-sm font-semibold text-white transition-colors truncate">
                  {t.navTickets}
                </h3>
                <p className="mt-0.5 sm:mt-1 text-[11px] sm:text-xs text-neutral-400 leading-relaxed line-clamp-2">
                  {locale === 'fr'
                    ? 'Suivi de vos demandes et réponses des agents.'
                    : 'Track your requests and specialist replies.'}
                </p>
              </div>
              <div className="sm:mt-3 flex items-center text-[11px] font-medium text-neutral-400 group-hover:text-white shrink-0 group-hover:translate-x-0.5 transition-all">
                <span className="hidden sm:inline mr-1">{locale === 'fr' ? 'Voir l’état' : 'Check status'}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </div>
          </Card>
        </Link>

        <Link href="/crypto" className="group block">
          <Card elevated hoverable className="p-3.5 sm:p-5 h-full transition-all">
            <div className="flex items-center gap-3.5 sm:flex-col sm:items-start sm:gap-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] sm:mb-2.5 group-hover:bg-white group-hover:text-black transition-all">
                <TrendingUp className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-xs sm:text-sm font-semibold text-white transition-colors truncate">
                  {t.navCrypto}
                </h3>
                <p className="mt-0.5 sm:mt-1 text-[11px] sm:text-xs text-neutral-400 leading-relaxed line-clamp-2">
                  {locale === 'fr'
                    ? 'Cours en temps réel BTC, ETH, FIRO, SOL, LTC.'
                    : 'Live rates for BTC, ETH, FIRO, SOL, LTC.'}
                </p>
              </div>
              <div className="sm:mt-3 flex items-center text-[11px] font-medium text-neutral-400 group-hover:text-white shrink-0 group-hover:translate-x-0.5 transition-all">
                <span className="hidden sm:inline mr-1">{locale === 'fr' ? 'Marché' : 'Rates'}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </div>
          </Card>
        </Link>

        <a
          href="https://t.me/STACK_WALLET_BOT"
          target="_blank"
          rel="noopener noreferrer"
          className="group block"
        >
          <Card elevated hoverable className="p-3.5 sm:p-5 h-full transition-all">
            <div className="flex items-center gap-3.5 sm:flex-col sm:items-start sm:gap-0">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] sm:mb-2.5 group-hover:bg-white group-hover:text-black transition-all">
                <Headphones className="h-4 w-4" />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-xs sm:text-sm font-semibold text-white transition-colors truncate">
                  {locale === 'fr' ? 'Assistance Telegram' : 'Telegram Support'}
                </h3>
                <p className="mt-0.5 sm:mt-1 text-[11px] sm:text-xs text-neutral-400 leading-relaxed line-clamp-2">
                  {locale === 'fr'
                    ? 'Échangez avec l’équipe et la communauté.'
                    : 'Direct assistance & community help.'}
                </p>
              </div>
              <div className="sm:mt-3 flex items-center text-[11px] font-medium text-neutral-400 group-hover:text-white shrink-0 group-hover:translate-x-0.5 transition-all">
                <span className="hidden sm:inline mr-1">{locale === 'fr' ? 'Rejoindre' : 'Join'}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </div>
          </Card>
        </a>
      </div>

      {/* Direct Specialist Assistance Bar */}
      {!showEscalation && (
        <div className="mt-8 rounded-2xl bg-white/[0.03] backdrop-blur-2xl border border-white/[0.09] p-4 sm:p-5 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-2xl">
          <div className="text-center sm:text-left">
            <h3 className="text-xs sm:text-sm font-semibold text-white">
              {locale === 'fr' ? 'Besoin d’aide supplémentaire ?' : 'Need further assistance?'}
            </h3>
            <p className="text-[11px] sm:text-xs text-neutral-400 mt-0.5">
              {locale === 'fr'
                ? 'Nos spécialistes vous assistent directement via Telegram et Email.'
                : 'Our specialists are available to answer your questions.'}
            </p>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => {
              triggerHaptic('medium');
              setShowEscalation(true);
            }}
            className="w-full sm:w-auto shrink-0 shadow-lg shadow-white/10"
          >
            <Headphones className="h-3.5 w-3.5 mr-1.5" />
            {locale === 'fr' ? 'Contacter le support' : 'Contact support'}
          </Button>
        </div>
      )}
    </div>
  );
}
