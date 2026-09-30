'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { QueryResponse } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
import { AnswerCard } from '@/components/support/AnswerCard';
import { TicketForm } from '@/components/tickets/TicketForm';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';
import {
  SpotlightCard,
  ShinyText,
  CountUp,
  BorderGlow,
  PixelCard,
} from '@/components/reactbits';
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
  ExternalLink,
  Clock,
  ChevronRight,
  Activity,
  CheckCircle2,
  Lock,
  Layers,
  Radio,
  ShieldAlert,
  EyeOff,
} from 'lucide-react';

const CATEGORY_PILLS_FR = [
  { label: 'Restauration Seed', icon: KeyRound, query: 'Comment restaurer mon portefeuille avec la phrase de récupération de 24 mots ?' },
  { label: 'Nœuds Monero & BTC', icon: Server, query: 'Comment configurer un nœud distant Monero ou Bitcoin privé ?' },
  { label: 'Swaps Non-Custodial', icon: ArrowLeftRight, query: 'Comment fonctionne l’échange intégré sans tiers de confiance ?' },
  { label: 'Frais & Mempool', icon: Layers, query: 'Que faire si ma transaction est en attente ou bloquée dans la mempool ?' },
  { label: 'Sécurité & Chiffrement', icon: ShieldCheck, query: 'Comment sécuriser mes clés privées et activer le chiffrement biométrique ?' },
];

const CATEGORY_PILLS_EN = [
  { label: 'Seed Recovery', icon: KeyRound, query: 'How do I restore my wallet using my 24-word recovery phrase?' },
  { label: 'Monero & BTC Nodes', icon: Server, query: 'How to configure a private remote Monero or Bitcoin node?' },
  { label: 'Non-Custodial Swaps', icon: ArrowLeftRight, query: 'How does the built-in non-custodial exchange work?' },
  { label: 'Fees & Mempool', icon: Layers, query: 'What to do if my transaction is pending or stuck in the mempool?' },
  { label: 'Security & Encryption', icon: ShieldCheck, query: 'How to securely store private keys and enable biometric lock?' },
];

interface GuideItem {
  id: string;
  category: 'security' | 'nodes' | 'transactions' | 'swaps';
  titleFr: string;
  titleEn: string;
  descFr: string;
  descEn: string;
  readTime: string;
  tagFr: string;
  tagEn: string;
  queryFr: string;
  queryEn: string;
}

const FEATURED_GUIDES: GuideItem[] = [
  {
    id: 'seed-restore',
    category: 'security',
    titleFr: 'Restauration sécurisée depuis la phrase de 24 mots',
    titleEn: 'Secure wallet restore using your 24-word seed',
    descFr: 'Procédure étape par étape pour réimporter vos clés privées sans jamais exposer vos mots à des applications tierces.',
    descEn: 'Step-by-step procedure to re-import your private keys without exposing credentials to third-party software.',
    readTime: '3 min',
    tagFr: 'Sécurité & Clés',
    tagEn: 'Security & Keys',
    queryFr: 'Comment restaurer mon portefeuille avec la phrase de récupération de 24 mots ?',
    queryEn: 'How do I restore my wallet using my 24-word recovery phrase?',
  },
  {
    id: 'remote-nodes',
    category: 'nodes',
    titleFr: 'Connexion à votre nœud distant Monero ou Bitcoin Core',
    titleEn: 'Connecting to your private remote Monero or Bitcoin node',
    descFr: 'Paramétrage des ports RPC, chiffrement SSL et synchronisation autonome pour préserver l’anonymat de vos transactions.',
    descEn: 'Configuring RPC endpoints, SSL encryption, and direct blockchain broadcast for complete sovereignty.',
    readTime: '4 min',
    tagFr: 'Nœuds & Réseau',
    tagEn: 'Nodes & Network',
    queryFr: 'Comment configurer un nœud distant Monero ou Bitcoin privé ?',
    queryEn: 'How to configure a private remote Monero or Bitcoin node?',
  },
  {
    id: 'mempool-rbf',
    category: 'transactions',
    titleFr: 'Diagnostic de transaction bloquée & accélération RBF',
    titleEn: 'Pending transaction diagnostics & Replace-by-Fee (RBF)',
    descFr: 'Analyse des frais du mempool, vérification des confirmations on-chain et procédure d’augmentation des frais.',
    descEn: 'Mempool fee estimation, on-chain confirmation checks, and fee bumping procedures.',
    readTime: '2 min',
    tagFr: 'Transactions',
    tagEn: 'Transactions',
    queryFr: 'Que faire si ma transaction est en attente ou bloquée dans la mempool ?',
    queryEn: 'What to do if my transaction is pending or stuck in the mempool?',
  },
  {
    id: 'local-backup',
    category: 'security',
    titleFr: 'Sauvegarde chiffrée AES-256 locale & verrouillage biométrique',
    titleEn: 'Local AES-256 encrypted backup & biometric lock',
    descFr: 'Verrouillage de la base de données locale par FaceID / empreinte et export chiffré sans aucun passage par le cloud.',
    descEn: 'Securing the local database with biometric authentication and encrypted offline exports.',
    readTime: '3 min',
    tagFr: 'Protection',
    tagEn: 'Protection',
    queryFr: 'Comment sécuriser mes clés privées et activer le chiffrement biométrique ?',
    queryEn: 'How to securely store private keys and enable biometric lock?',
  },
  {
    id: 'atomic-swaps',
    category: 'swaps',
    titleFr: 'Échanges décentralisés de devises sans intermédiaire (Swaps)',
    titleEn: 'Non-custodial peer-to-peer crypto swaps',
    descFr: 'Comprendre l’exécution des swaps directs (BTC, XMR, ETH) et la validation des taux de conversion sans intermédiaire.',
    descEn: 'How peer-to-peer non-custodial swaps execute without custody risks or counterparty exposure.',
    readTime: '4 min',
    tagFr: 'Swaps',
    tagEn: 'Swaps',
    queryFr: 'Comment fonctionne l’échange intégré sans tiers de confiance ?',
    queryEn: 'How does the built-in non-custodial exchange work?',
  },
];

export default function HomePage() {
  const { locale, t } = useTranslation();
  const { triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showEscalation, setShowEscalation] = useState(false);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<'all' | 'security' | 'nodes' | 'transactions' | 'swaps'>('all');

  const pills = locale === 'fr' ? CATEGORY_PILLS_FR : CATEGORY_PILLS_EN;

  const handleSearch = async (searchQuery: string) => {
    if (!searchQuery.trim()) return;

    setIsLoading(true);
    setError(null);
    setShowEscalation(false);
    triggerHaptic('light');

    try {
      const res = await api.querySupport({ query: searchQuery.trim(), language: locale });
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

  const handlePillClick = (suggestedQuery: string) => {
    setQuery(suggestedQuery);
    handleSearch(suggestedQuery);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleClear = () => {
    setQuery('');
    setResult(null);
    setError(null);
    setShowEscalation(false);
  };

  const isSearchActive = Boolean(result || showEscalation || error);

  const filteredGuides = FEATURED_GUIDES.filter((guide) => {
    if (selectedCategoryFilter === 'all') return true;
    return guide.category === selectedCategoryFilter;
  });

  return (
    <div className="mx-auto max-w-7xl px-3.5 py-6 sm:px-6 lg:px-8 lg:py-12">
      {/* Hero Section - Lightweight on mobile, expansive on desktop */}
      <div className="text-center mb-6 sm:mb-12">
        <h1 className="text-2xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white max-w-4xl mx-auto leading-tight">
          {t.heroTitle}
        </h1>
        <p className="mt-2 sm:mt-4 max-w-2xl mx-auto text-xs sm:text-base text-zinc-400 leading-relaxed font-normal">
          <span className="sm:hidden">
            {locale === 'fr'
              ? 'Recherchez une solution vérifiée ou contactez nos ingénieurs.'
              : 'Find verified solutions or reach protocol engineers.'}
          </span>
          <span className="hidden sm:inline">
            {t.heroSubtitle}
          </span>
        </p>

        {/* Command Search Box with BorderGlow */}
        <div className="mt-5 sm:mt-8 max-w-3xl mx-auto">
          <BorderGlow
            borderRadius={18}
            glowColor="rgba(255, 255, 255, 0.2)"
            backgroundColor="#0c0c0f"
            className="shadow-2xl shadow-black/80"
          >
            <form onSubmit={onSubmit} className="relative flex items-center p-1 sm:p-1.5">
              <div className="relative w-full flex items-center">
                <Search className="absolute left-3.5 sm:left-5 h-4 w-4 text-zinc-400 pointer-events-none" />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={t.searchPlaceholder}
                  className="w-full bg-transparent pl-10 sm:pl-12 pr-24 sm:pr-36 py-2.5 sm:py-3.5 text-xs sm:text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none"
                />
                {query && (
                  <button
                    type="button"
                    onClick={handleClear}
                    className="absolute right-20 sm:right-32 p-1.5 text-zinc-400 hover:text-white transition-colors cursor-pointer"
                    title="Effacer"
                    aria-label={t.clearSearch}
                  >
                    <X className="h-4 w-4" />
                  </button>
                )}
                <div className="absolute right-1">
                  <Button
                    type="submit"
                    variant="primary"
                    size="sm"
                    isLoading={isLoading}
                    className="rounded-xl px-3 py-1.5 sm:px-4 sm:py-2 text-xs font-semibold"
                  >
                    {t.searchButton}
                  </Button>
                </div>
              </div>
            </form>
          </BorderGlow>

          {/* Interactive Category Filter Pills - Smooth Horizontal Scroll on Mobile */}
          <div className="mt-3 sm:mt-4 flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-1.5 pt-1 no-scrollbar sm:flex-wrap sm:justify-center px-1">
            <span className="text-[11px] sm:text-xs text-zinc-500 font-medium whitespace-nowrap shrink-0 mr-0.5">
              {t.popularQueries}
            </span>
            {pills.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.label}
                  type="button"
                  onClick={() => handlePillClick(item.query)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-[#0c0c0f] px-2.5 py-1 sm:px-3 sm:py-1.5 text-[11px] sm:text-xs text-zinc-300 transition-all hover:border-white/20 hover:text-white hover:bg-white/[0.04] active:scale-95 cursor-pointer shadow-sm whitespace-nowrap shrink-0"
                >
                  <Icon className="h-3 w-3 sm:h-3.5 sm:w-3.5 text-zinc-400" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Bento Grid: 4 Core Architecture Indicators - Streamlined on Mobile, Detailed on Desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4 mb-8 sm:mb-10">
        <SpotlightCard className="p-3 sm:p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <div className="flex h-7 w-7 sm:h-9 sm:w-9 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.08]">
              <Clock className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </div>
            <Badge variant="neutral" size="xs">
              {locale === 'fr' ? 'Délai moyen' : 'Average delay'}
            </Badge>
          </div>
          <div className="mt-3 sm:mt-4">
            <div className="text-base sm:text-2xl font-bold tracking-tight text-white">
              &lt; 1 min
            </div>
            <div className="text-[11px] sm:text-xs font-medium text-zinc-300 mt-0.5">{t.kpiResponseTime}</div>
            <div className="hidden sm:block text-[11px] text-zinc-500 mt-0.5">{t.kpiResponseSub}</div>
          </div>
        </SpotlightCard>

        <SpotlightCard className="p-3 sm:p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <div className="flex h-7 w-7 sm:h-9 sm:w-9 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.08]">
              <Lock className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </div>
            <Badge variant="shiny" size="xs">
              {locale === 'fr' ? 'Souverain' : 'Sovereign'}
            </Badge>
          </div>
          <div className="mt-3 sm:mt-4">
            <div className="text-base sm:text-2xl font-bold tracking-tight text-white">
              <CountUp to={100} duration={1.5} suffix="%" />
            </div>
            <div className="text-[11px] sm:text-xs font-medium text-zinc-300 mt-0.5">{t.kpiResolutionRate}</div>
            <div className="hidden sm:block text-[11px] text-zinc-500 mt-0.5">{t.kpiResolutionSub}</div>
          </div>
        </SpotlightCard>

        <SpotlightCard className="p-3 sm:p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <div className="flex h-7 w-7 sm:h-9 sm:w-9 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.08]">
              <Activity className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-zinc-200" />
            </div>
            <Badge variant="neutral" size="xs">
              {locale === 'fr' ? 'Démons actifs' : 'Active daemons'}
            </Badge>
          </div>
          <div className="mt-3 sm:mt-4">
            <div className="text-base sm:text-2xl font-bold tracking-tight text-white">
              <CountUp to={99.98} decimals={2} duration={2} suffix="%" />
            </div>
            <div className="text-[11px] sm:text-xs font-medium text-zinc-300 mt-0.5">{t.kpiUptime}</div>
            <div className="hidden sm:block text-[11px] text-zinc-500 mt-0.5">{t.kpiUptimeSub}</div>
          </div>
        </SpotlightCard>

        <SpotlightCard className="p-3 sm:p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <div className="flex h-7 w-7 sm:h-9 sm:w-9 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.08]">
              <ShieldCheck className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
            </div>
            <Badge variant="brand" size="xs">
              {locale === 'fr' ? 'Assistance' : 'Assistance'}
            </Badge>
          </div>
          <div className="mt-3 sm:mt-4">
            <div className="text-base sm:text-2xl font-bold tracking-tight text-white">{t.kpiSupportVal}</div>
            <div className="text-[11px] sm:text-xs font-medium text-zinc-300 mt-0.5">{t.kpiSupportHours}</div>
            <div className="hidden sm:block text-[11px] text-zinc-500 mt-0.5">{t.kpiSupportSub}</div>
          </div>
        </SpotlightCard>
      </div>

      {/* Active Search / Result / Escalation View: 2-Column Responsive Layout */}
      {isSearchActive && (
        <div className="mb-10 sm:mb-12">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
            {/* Main Column: Result or Escalation Form (lg:col-span-8) */}
            <div className="lg:col-span-8 space-y-6">
              {error && (
                <Alert type="error" title={t.searchErrorTitle}>
                  {error}
                </Alert>
              )}

              {result && !showEscalation && (
                <div>
                  <AnswerCard
                    result={result}
                    onEscalate={() => setShowEscalation(true)}
                  />
                </div>
              )}

              {showEscalation && (
                <div>
                  <TicketForm
                    initialQuestion={query}
                    initialAutomatedAnswer={result?.answer}
                    onCancel={() => setShowEscalation(false)}
                    onSuccess={(ticket) => {
                      toast({
                        title: locale === 'fr' ? 'Ticket créé avec succès' : 'Ticket created successfully',
                        description: `Référence #${ticket.id}`,
                        variant: 'success',
                      });
                    }}
                  />
                </div>
              )}
            </div>

            {/* Contextual Sidebar Column (lg:col-span-4) */}
            <div className="lg:col-span-4 space-y-6">
              <Card elevated spotlight className="p-4 sm:p-5 border-white/[0.09] space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-white/[0.08]">
                  <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                    {locale === 'fr' ? 'Besoin d’aide immédiate ?' : 'Need direct help?'}
                  </h3>
                  <button
                    onClick={handleClear}
                    className="text-xs text-zinc-400 hover:text-white transition-colors cursor-pointer"
                  >
                    {locale === 'fr' ? 'Réinitialiser' : 'Reset search'}
                  </button>
                </div>

                <p className="text-xs text-zinc-400 leading-relaxed">
                  {locale === 'fr'
                    ? 'Notre équipe d’ingénieurs est disponible 7j/7 sur le canal Telegram officiel pour vous assister en cas d’urgence sur vos transactions.'
                    : 'Our engineering team is active 7 days a week on Telegram to diagnose complex issues and unconfirmed transactions.'}
                </p>

                <div className="pt-2 space-y-2">
                  <a
                    href="https://t.me/STACK_WALLET_BOT"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-white/[0.08] hover:border-white/[0.2] hover:bg-zinc-850 text-xs font-medium text-zinc-200 hover:text-white transition-all"
                  >
                    <span className="flex items-center gap-2">
                      <Headphones className="h-4 w-4 text-zinc-300" />
                      <span>{locale === 'fr' ? 'Assistance Telegram' : 'Telegram Support'}</span>
                    </span>
                    <ExternalLink className="h-3.5 w-3.5 text-zinc-500" />
                  </a>

                  <Link
                    href="/tickets"
                    className="flex items-center justify-between p-3 rounded-xl bg-zinc-900 border border-white/[0.08] hover:border-white/[0.2] hover:bg-zinc-850 text-xs font-medium text-zinc-200 hover:text-white transition-all"
                  >
                    <span className="flex items-center gap-2">
                      <Ticket className="h-4 w-4 text-zinc-300" />
                      <span>{t.navTickets}</span>
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-zinc-500" />
                  </Link>
                </div>
              </Card>

              {/* Security Reminder */}
              <div className="rounded-2xl bg-[#0c0c0f] border border-white/[0.08] p-4 flex items-start gap-3 text-xs text-zinc-400">
                <ShieldCheck className="h-5 w-5 text-zinc-300 shrink-0 mt-0.5" />
                <p>
                  {t.ticketSecurityWarning}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 4 Primary Workspaces Bento Grid - Clean 2x2 grid on mobile, relaxed and fast to navigate */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-5 mt-4 sm:mt-6 mb-8 sm:mb-12">
        <Link href="/knowledge" className="group block">
          <SpotlightCard className="p-3.5 sm:p-5 h-full transition-all group-hover:border-white/[0.2]">
            <div className="flex flex-col h-full justify-between">
              <div>
                <div className="flex h-8 w-8 sm:h-11 sm:w-11 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.1] mb-2.5 sm:mb-4 group-hover:bg-white group-hover:text-black group-hover:border-white transition-all shadow-sm">
                  <BookOpen className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors">
                  {t.navKnowledge}
                </h3>
                <p className="hidden sm:block mt-1.5 text-xs text-zinc-400 leading-relaxed font-normal">
                  {locale === 'fr'
                    ? 'Procédures techniques détaillées, configuration de nœuds distants et résolutions documentées.'
                    : 'Verified technical guides, remote node setups, and step-by-step procedures.'}
                </p>
              </div>
              <div className="mt-2.5 sm:mt-4 pt-2 sm:pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] sm:text-xs font-medium text-zinc-400 group-hover:text-white transition-colors">
                <span>{locale === 'fr' ? 'Consulter' : 'Explore'}</span>
                <ArrowRight className="h-3 w-3 sm:h-3.5 sm:w-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </SpotlightCard>
        </Link>

        <Link href="/tickets" className="group block">
          <SpotlightCard className="p-3.5 sm:p-5 h-full transition-all group-hover:border-white/[0.2]">
            <div className="flex flex-col h-full justify-between">
              <div>
                <div className="flex h-8 w-8 sm:h-11 sm:w-11 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.1] mb-2.5 sm:mb-4 group-hover:bg-white group-hover:text-black group-hover:border-white transition-all shadow-sm">
                  <Ticket className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors">
                  {t.navTickets}
                </h3>
                <p className="hidden sm:block mt-1.5 text-xs text-zinc-400 leading-relaxed font-normal">
                  {locale === 'fr'
                    ? 'Suivi de vos demandes d’assistance, réponses des techniciens et résolutions archivées.'
                    : 'Track open tickets, collaborate with specialists, and review confirmed resolutions.'}
                </p>
              </div>
              <div className="mt-2.5 sm:mt-4 pt-2 sm:pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] sm:text-xs font-medium text-zinc-400 group-hover:text-white transition-colors">
                <span>{locale === 'fr' ? 'Mes tickets' : 'Tickets'}</span>
                <ArrowRight className="h-3 w-3 sm:h-3.5 sm:w-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </SpotlightCard>
        </Link>

        <Link href="/crypto" className="group block">
          <SpotlightCard className="p-3.5 sm:p-5 h-full transition-all group-hover:border-white/[0.2]">
            <div className="flex flex-col h-full justify-between">
              <div>
                <div className="flex h-8 w-8 sm:h-11 sm:w-11 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.1] mb-2.5 sm:mb-4 group-hover:bg-white group-hover:text-black group-hover:border-white transition-all shadow-sm">
                  <TrendingUp className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors">
                  {t.navCrypto}
                </h3>
                <p className="hidden sm:block mt-1.5 text-xs text-zinc-400 leading-relaxed font-normal">
                  {locale === 'fr'
                    ? 'Cours en temps réel BTC, XMR, ETH, SOL, LTC, DOGE et métriques on-chain.'
                    : 'Real-time price streams for BTC, XMR, ETH, SOL, LTC, DOGE with 24h trends.'}
                </p>
              </div>
              <div className="mt-2.5 sm:mt-4 pt-2 sm:pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] sm:text-xs font-medium text-zinc-400 group-hover:text-white transition-colors">
                <span>{locale === 'fr' ? 'Marchés' : 'Markets'}</span>
                <ArrowRight className="h-3 w-3 sm:h-3.5 sm:w-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </SpotlightCard>
        </Link>

        <a
          href="https://t.me/STACK_WALLET_BOT"
          target="_blank"
          rel="noopener noreferrer"
          className="group block"
        >
          <SpotlightCard className="p-3.5 sm:p-5 h-full transition-all group-hover:border-white/[0.2]">
            <div className="flex flex-col h-full justify-between">
              <div>
                <div className="flex h-8 w-8 sm:h-11 sm:w-11 items-center justify-center rounded-lg sm:rounded-xl bg-zinc-900 text-zinc-200 border border-white/[0.1] mb-2.5 sm:mb-4 group-hover:bg-white group-hover:text-black group-hover:border-white transition-all shadow-sm">
                  <Headphones className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <h3 className="text-xs sm:text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors">
                  {locale === 'fr' ? 'Chat Telegram' : 'Telegram Chat'}
                </h3>
                <p className="hidden sm:block mt-1.5 text-xs text-zinc-400 leading-relaxed font-normal">
                  {locale === 'fr'
                    ? 'Assistance directe en direct avec les mainteneurs du projet et la communauté internationale.'
                    : 'Direct assistance with protocol developers and the international community.'}
                </p>
              </div>
              <div className="mt-2.5 sm:mt-4 pt-2 sm:pt-3 border-t border-white/[0.06] flex items-center justify-between text-[11px] sm:text-xs font-medium text-zinc-400 group-hover:text-white transition-colors">
                <span>{locale === 'fr' ? 'Rejoindre' : 'Open'}</span>
                <ExternalLink className="h-3 w-3 sm:h-3.5 sm:w-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </div>
          </SpotlightCard>
        </a>
      </div>

      {/* Spacious 2-Column Architecture: Verified Guides + Node Status & Support Dispatch */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        {/* Left Column: Essential Guides & Procedures (lg:col-span-8) */}
        <div className="lg:col-span-8 space-y-4 sm:space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4 pb-2 border-b border-white/[0.08]">
            <div>
              <h2 className="text-sm sm:text-lg font-bold text-white tracking-tight">
                <ShinyText
                  text={locale === 'fr' ? 'Procédures Techniques Vérifiées' : 'Verified Technical Procedures'}
                  speed={5}
                  color="#d4d4d8"
                  shineColor="#ffffff"
                />
              </h2>
              <p className="hidden sm:block text-xs text-zinc-400 mt-0.5">
                {locale === 'fr'
                  ? 'Fiches documentées étape par étape par l’équipe technique Stack Wallet.'
                  : 'Step-by-step procedures documented by the Stack Wallet engineering team.'}
              </p>
            </div>

            {/* Filter pills - Horizontal scroll on mobile */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 no-scrollbar">
              {(
                [
                  { id: 'all', label: locale === 'fr' ? 'Tous' : 'All' },
                  { id: 'security', label: locale === 'fr' ? 'Sécurité' : 'Security' },
                  { id: 'nodes', label: locale === 'fr' ? 'Nœuds' : 'Nodes' },
                  { id: 'transactions', label: locale === 'fr' ? 'Mempool' : 'Mempool' },
                  { id: 'swaps', label: locale === 'fr' ? 'Swaps' : 'Swaps' },
                ] as const
              ).map((f) => (
                <button
                  key={f.id}
                  onClick={() => {
                    triggerHaptic('light');
                    setSelectedCategoryFilter(f.id);
                  }}
                  className={`px-2.5 py-1 sm:px-3 sm:py-1.5 rounded-lg text-[11px] sm:text-xs font-medium transition-all cursor-pointer whitespace-nowrap ${
                    selectedCategoryFilter === f.id
                      ? 'bg-white text-black font-semibold shadow-sm border border-white'
                      : 'bg-[#0c0c0f] border border-white/[0.08] text-zinc-400 hover:text-white hover:bg-white/[0.04]'
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2.5 sm:space-y-3">
            {filteredGuides.map((item) => (
              <div
                key={item.id}
                onClick={() => handlePillClick(locale === 'fr' ? item.queryFr : item.queryEn)}
                className="group relative rounded-xl sm:rounded-2xl bg-[#0c0c0f] border border-white/[0.08] p-3.5 sm:p-5 hover:border-white/20 hover:bg-[#111115] transition-all cursor-pointer shadow-sm hover:shadow-md"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="space-y-1 sm:space-y-2 min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 sm:gap-2">
                      <span className="px-1.5 py-0.5 sm:px-2 rounded text-[10px] sm:text-[11px] font-semibold bg-white/[0.08] text-zinc-200 border border-white/[0.12]">
                        {locale === 'fr' ? item.tagFr : item.tagEn}
                      </span>
                      <span className="flex items-center gap-1 text-[10px] sm:text-[11px] text-zinc-300 font-medium">
                        <CheckCircle2 className="h-3 w-3" />
                        <span>{locale === 'fr' ? 'Vérifié' : 'Verified'}</span>
                      </span>
                      <span className="text-[10px] sm:text-[11px] text-zinc-500 font-mono">
                        {item.readTime}
                      </span>
                    </div>

                    <h4 className="text-xs sm:text-sm font-semibold text-zinc-100 group-hover:text-white transition-colors leading-snug">
                      {locale === 'fr' ? item.titleFr : item.titleEn}
                    </h4>

                    {/* Relaxed text: 1 clamped line on mobile, full text on desktop */}
                    <p className="text-[11px] sm:text-xs text-zinc-400 leading-relaxed font-normal line-clamp-1 sm:line-clamp-none">
                      {locale === 'fr' ? item.descFr : item.descEn}
                    </p>
                  </div>

                  <div className="flex items-center gap-1.5 self-center shrink-0">
                    <Button
                      variant="secondary"
                      size="xs"
                      className="hidden sm:inline-flex group-hover:border-white/[0.3] group-hover:text-white pointer-events-none text-xs"
                    >
                      <span>{locale === 'fr' ? 'Consulter' : 'Read Guide'}</span>
                      <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
                    </Button>
                    <ChevronRight className="sm:hidden h-4 w-4 text-zinc-500 group-hover:text-white transition-colors" />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="pt-2 flex items-center justify-between text-xs text-zinc-400">
            <span className="hidden sm:inline">
              {locale === 'fr' ? 'Vous ne trouvez pas la solution requise ?' : 'Can’t find the exact procedure?'}
            </span>
            <Link
              href="/knowledge"
              className="text-zinc-200 hover:text-white font-medium flex items-center gap-1 transition-colors text-xs ml-auto sm:ml-0"
            >
              <span>{locale === 'fr' ? 'Voir toutes les fiches' : 'Browse all guides'}</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* Right Column: Node Status, Security Rules & Direct Escalation (lg:col-span-4) */}
        <div className="lg:col-span-4 space-y-4 sm:space-y-6">
          {/* Node Health Telemetry Widget with BorderGlow */}
          <BorderGlow
            borderRadius={16}
            glowColor="rgba(255, 255, 255, 0.25)"
            backgroundColor="#0c0c0f"
          >
            <div className="p-3.5 sm:p-5">
              <div className="flex items-center justify-between pb-2.5 sm:pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <Radio className="h-3.5 w-3.5 sm:h-4 sm:w-4 text-zinc-300" />
                  <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                    {t.nodeStatusTitle}
                  </h3>
                </div>
                <Badge variant="neutral" size="xs">
                  Live
                </Badge>
              </div>

              <div className="mt-3 sm:mt-4 space-y-2.5 sm:space-y-3">
                {/* Bitcoin Core */}
                <div className="p-2.5 sm:p-3 rounded-xl bg-zinc-900 border border-white/[0.06] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-zinc-200">
                      Bitcoin Core
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                      <CountUp to={892140} separator="," prefix="Bloc #" duration={2} /> • 14 sat/vB
                    </div>
                  </div>
                  <span className="text-[10px] sm:text-[11px] font-medium text-zinc-300 bg-white/[0.06] px-2 py-0.5 rounded border border-white/[0.1]">
                    {t.synced}
                  </span>
                </div>

                {/* Monero Daemon */}
                <div className="p-2.5 sm:p-3 rounded-xl bg-zinc-900 border border-white/[0.06] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-zinc-200">
                      Monero Daemon
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono mt-0.5">
                      <CountUp to={3124800} separator="," prefix="Bloc #" duration={2.5} /> • 24 peers
                    </div>
                  </div>
                  <span className="text-[10px] sm:text-[11px] font-medium text-zinc-300 bg-white/[0.06] px-2 py-0.5 rounded border border-white/[0.1]">
                    {t.synced}
                  </span>
                </div>

                {/* Solana RPC */}
                <div className="p-2.5 sm:p-3 rounded-xl bg-zinc-900 border border-white/[0.06] flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-zinc-200">
                      Solana RPC
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono mt-0.5">Slot #290,410,200 • 2,750 TPS</div>
                  </div>
                  <span className="text-[10px] sm:text-[11px] font-medium text-zinc-300 bg-white/[0.06] px-2 py-0.5 rounded border border-white/[0.1]">
                    {t.synced}
                  </span>
                </div>
              </div>
            </div>
          </BorderGlow>

          {/* Security & Non-Custodial Core Principles with PixelCard */}
          <PixelCard className="p-3.5 sm:p-5 space-y-3 sm:space-y-4">
            <div className="flex items-center gap-2.5 pb-2.5 sm:pb-3 border-b border-white/[0.08]">
              <div className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg bg-zinc-850 text-zinc-200 border border-white/[0.08]">
                <Lock className="h-3.5 w-3.5 sm:h-4 sm:w-4" />
              </div>
              <div>
                <h3 className="text-xs font-semibold text-zinc-200 uppercase tracking-wider">
                  {t.securityCardTitle}
                </h3>
                <p className="text-[10px] sm:text-[11px] text-zinc-500">{t.securityCardSub}</p>
              </div>
            </div>

            <ul className="space-y-2 sm:space-y-2.5 text-xs text-zinc-400">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="h-3.5 w-3.5 text-zinc-300 shrink-0 mt-0.5" />
                <span className="leading-snug sm:leading-relaxed text-[11px] sm:text-xs">{t.securityRule1}</span>
              </li>
              <li className="flex items-start gap-2">
                <ShieldAlert className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                <span className="leading-snug sm:leading-relaxed text-[11px] sm:text-xs">{t.securityRule2}</span>
              </li>
              <li className="flex items-start gap-2">
                <EyeOff className="h-3.5 w-3.5 text-zinc-400 shrink-0 mt-0.5" />
                <span className="leading-snug sm:leading-relaxed text-[11px] sm:text-xs">{t.securityRule3}</span>
              </li>
            </ul>
          </PixelCard>
        </div>
      </div>

      {/* Full-Width Assistance & Community Hub - Fully exploits space, highly comforting and generous */}
      <div className="mt-6 sm:mt-12">
        <SpotlightCard className="p-4 sm:p-8 border-white/[0.1] bg-[#0c0c0f]">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 lg:gap-10 items-start">
            {/* Left Col: Direct Concierge & Immediate Actions (7 cols) */}
            <div className="lg:col-span-7 space-y-3.5 sm:space-y-5">
              <div className="flex items-center gap-2">
                <span className="px-2.5 py-1 rounded-full bg-white/[0.08] text-white text-[11px] font-semibold uppercase tracking-wider border border-white/[0.12]">
                  {locale === 'fr' ? 'Assistance Directe • 7j/7' : 'Direct Assistance • 24/7'}
                </span>
                <span className="text-xs text-zinc-400">
                  {locale === 'fr' ? 'Équipe d’ingénieurs' : 'Core engineering team'}
                </span>
              </div>

              <div>
                <h3 className="text-base sm:text-2xl font-bold tracking-tight text-white leading-snug">
                  {locale === 'fr'
                    ? 'Une question sur vos transactions ou vos clés ?'
                    : 'Questions regarding your transactions or keys?'}
                </h3>
                <p className="mt-1.5 sm:mt-2 text-xs sm:text-sm text-zinc-400 leading-relaxed font-normal">
                  {locale === 'fr'
                    ? 'Nos ingénieurs et mainteneurs open-source vous accompagnent directement pour diagnostiquer vos transactions, configurer vos nœuds ou sécuriser votre portefeuille en toute confidentialité.'
                    : 'Our open-source engineers provide non-custodial assistance to diagnose transactions, configure private nodes, and secure your wallet.'}
                </p>
              </div>

              <div className="pt-1 sm:pt-2 flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 sm:gap-3">
                <Button
                  variant="primary"
                  size="md"
                  onClick={() => {
                    triggerHaptic('medium');
                    setShowEscalation(true);
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  className="justify-center shadow-lg"
                >
                  <Ticket className="h-4 w-4 mr-2" />
                  <span>{t.btnSubmitTicket}</span>
                </Button>

                <a
                  href="https://t.me/STACK_WALLET_BOT"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block sm:inline-block"
                >
                  <Button variant="secondary" size="md" className="w-full justify-center">
                    <Headphones className="h-4 w-4 mr-2 text-zinc-300" />
                    <span>{locale === 'fr' ? 'Chat Telegram Officiel' : 'Official Telegram Chat'}</span>
                    <ExternalLink className="h-3.5 w-3.5 ml-2 text-zinc-500" />
                  </Button>
                </a>
              </div>

              {/* Sovereign Trust Pledge */}
              <div className="pt-2 flex flex-wrap items-center gap-y-2 gap-x-4 text-[11px] text-zinc-400">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3.5 w-3.5 text-zinc-300" />
                  <span>100% Non-Custodial</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <Lock className="h-3.5 w-3.5 text-zinc-300" />
                  <span>{locale === 'fr' ? 'Chiffrement local AES-256' : 'Local AES-256 encryption'}</span>
                </span>
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-3.5 w-3.5 text-zinc-300" />
                  <span>{locale === 'fr' ? 'Audit public GitHub' : 'Public GitHub audit'}</span>
                </span>
              </div>
            </div>

            {/* Right Col: 3 Emergency Reassurance Points (5 cols) */}
            <div className="lg:col-span-5 space-y-2.5 sm:space-y-3 pt-3 lg:pt-0 lg:border-l lg:border-white/[0.08] lg:pl-8">
              <h4 className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
                {locale === 'fr' ? 'Garanties & Réponses Immédiates' : 'Guarantees & Quick Answers'}
              </h4>

              <div className="space-y-2 sm:space-y-2.5">
                <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/[0.06]">
                  <div className="text-xs font-semibold text-zinc-200">
                    {locale === 'fr' ? 'Mes fonds sont-ils en sécurité ?' : 'Are my funds always safe?'}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed font-normal">
                    {locale === 'fr'
                      ? 'Oui. Vos fonds résident sur la blockchain et ne quittent jamais votre contrôle exclusif grâce à vos 24 mots.'
                      : 'Yes. Funds reside directly on-chain and remain exclusively under your control via your seed phrase.'}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/[0.06]">
                  <div className="text-xs font-semibold text-zinc-200">
                    {locale === 'fr' ? 'Quelqu’un peut-il demander ma seed ?' : 'Can support ask for my seed?'}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed font-normal">
                    {locale === 'fr'
                      ? 'Jamais. Aucun ingénieur ni membre de l’équipe ne vous demandera votre phrase secrète.'
                      : 'Never. No official engineer or team member will ever request your recovery phrase.'}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/[0.06]">
                  <div className="text-xs font-semibold text-zinc-200">
                    {locale === 'fr' ? 'Délai moyen d’intervention ?' : 'Average intervention delay?'}
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed font-normal">
                    {locale === 'fr'
                      ? 'Prise en charge rapide sur notre canal Telegram officiel et réponses suivies par ticket.'
                      : 'Fast triage on our official Telegram channel and tracked responses via ticket.'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </SpotlightCard>
      </div>
    </div>
  );
}
