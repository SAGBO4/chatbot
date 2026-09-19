'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { KnowledgeArticle } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { Badge } from '@/components/ui/Badge';
import {
  BookOpen,
  Plus,
  Search,
  RefreshCw,
  FileText,
  CheckCircle2,
  Calendar,
  X,
  Tag,
  HelpCircle,
  ArrowLeft,
  ShieldCheck,
} from 'lucide-react';
import Link from 'next/link';

export default function KnowledgePage() {
  const { t, locale } = useTranslation();
  const { isAdmin } = useTelegram();
  const [articles, setArticles] = useState<KnowledgeArticle[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingest Modal state (Admin only)
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newQuestion, setNewQuestion] = useState('');
  const [newSolution, setNewSolution] = useState('');
  const [newKeywords, setNewKeywords] = useState('');
  const [isIngesting, setIsIngesting] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [ingestSuccess, setIngestSuccess] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const limit = isAdmin ? 100 : 10;
      const articlesData = await api.getKnowledgeArticles(limit, 0);
      setArticles(articlesData);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errKbLoad;
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadErrorMessage = useRef(t.errKbLoad);
  useEffect(() => {
    loadErrorMessage.current = t.errKbLoad;
  }, [t.errKbLoad]);

  useEffect(() => {
    let ignore = false;
    const initData = async () => {
      try {
        const limit = isAdmin ? 100 : 10;
        const articlesData = await api.getKnowledgeArticles(limit, 0);
        if (!ignore) {
          setArticles(articlesData);
          setIsLoading(false);
        }
      } catch (err: unknown) {
        if (!ignore) {
          const msg = (err as { message?: string })?.message || loadErrorMessage.current;
          setError(msg);
          setIsLoading(false);
        }
      }
    };
    initData();
    return () => {
      ignore = true;
    };
  }, [isAdmin]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
  };

  const filteredArticles = articles.filter((art) =>
    art.question.toLowerCase().includes(search.toLowerCase()) ||
    art.solution.toLowerCase().includes(search.toLowerCase()) ||
    (art.keywords && art.keywords.toLowerCase().includes(search.toLowerCase()))
  );

  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newQuestion.trim() || !newSolution.trim()) return;

    setIsIngesting(true);
    setModalError(null);
    try {
      await api.ingestKnowledgeArticle({
        question: newQuestion.trim(),
        solution: newSolution.trim(),
        keywords: newKeywords.trim() || undefined,
      });
      setIngestSuccess(true);
      setNewQuestion('');
      setNewSolution('');
      setNewKeywords('');
      loadData();
      setTimeout(() => {
        setIsModalOpen(false);
        setIngestSuccess(false);
      }, 1500);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errKbAdd;
      setModalError(msg);
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:py-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-neutral-400 hover:text-white mb-2 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{t.navSupport}</span>
          </Link>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
              {isAdmin ? t.kbTitle : (locale === 'fr' ? 'Foire Aux Questions (FAQ)' : 'Frequently Asked Questions (FAQ)')}
            </h1>
            <span className={`rounded-full border px-2.5 py-0.5 text-[10px] font-medium ${
              isAdmin
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-white/10 border-white/20 text-white'
            }`}>
              {isAdmin ? 'Admin • Documentation' : (locale === 'fr' ? 'Top 10 FAQ' : 'Top 10 FAQ')}
            </span>
          </div>
          <p className="text-xs sm:text-sm text-neutral-400 mt-1">
            {isAdmin
              ? t.kbSub
              : (locale === 'fr'
                  ? 'Consultez les réponses aux 10 questions les plus fréquemment posées sur Stack Wallet.'
                  : 'Check the answers to the top 10 most frequently asked questions about Stack Wallet.')}
          </p>
        </div>

        {isAdmin && (
          <Button
            variant="primary"
            size="sm"
            className="w-full sm:w-auto justify-center"
            onClick={() => {
              setIsModalOpen(true);
              setModalError(null);
              setIngestSuccess(false);
            }}
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {t.btnAddArticle}
          </Button>
        )}
      </div>

      {/* Stats Cards - Compact 3-col on all screens */}
      <div className="grid grid-cols-3 gap-2 sm:gap-4 mb-6">
        <Card elevated className="p-2.5 sm:p-4 border-white/[0.08] flex flex-col sm:flex-row items-center sm:gap-3.5 text-center sm:text-left">
          <div className="flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] mb-1 sm:mb-0 shrink-0">
            <FileText className="h-4 w-4 sm:h-5 sm:w-5" />
          </div>
          <div>
            <div className="text-base sm:text-xl font-bold text-white">{articles.length}</div>
            <div className="text-[10px] sm:text-xs text-neutral-400 font-medium leading-tight truncate">
              {isAdmin ? t.statTotalArticles : (locale === 'fr' ? 'FAQ disponibles' : 'Available FAQs')}
            </div>
          </div>
        </Card>

        <Card elevated className="p-2.5 sm:p-4 border-white/[0.08] flex flex-col sm:flex-row items-center sm:gap-3.5 text-center sm:text-left">
          <div className="flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] mb-1 sm:mb-0 shrink-0">
            {isAdmin ? <CheckCircle2 className="h-4 w-4 sm:h-5 sm:w-5" /> : <ShieldCheck className="h-4 w-4 sm:h-5 sm:w-5" />}
          </div>
          <div>
            <div className="text-base sm:text-xl font-bold text-white">
              {isAdmin ? articles.filter((a) => a.source_ticket_id).length : '10 max'}
            </div>
            <div className="text-[10px] sm:text-xs text-neutral-400 font-medium leading-tight truncate">
              {isAdmin ? t.statResolvedTickets : (locale === 'fr' ? 'Sélection essentielle' : 'Essential limit')}
            </div>
          </div>
        </Card>

        <Card elevated className="p-2.5 sm:p-4 border-white/[0.08] flex flex-col sm:flex-row items-center sm:gap-3.5 text-center sm:text-left">
          <div className="flex h-8 w-8 sm:h-10 sm:w-10 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] mb-1 sm:mb-0 shrink-0">
            <BookOpen className="h-4 w-4 sm:h-5 sm:w-5" />
          </div>
          <div>
            <div className="text-base sm:text-xl font-bold text-white">100%</div>
            <div className="text-[10px] sm:text-xs text-neutral-400 font-medium leading-tight truncate">
              {isAdmin ? t.statCoverage : (locale === 'fr' ? 'Vérifiées' : 'Verified')}
            </div>
          </div>
        </Card>
      </div>

      {/* Search Bar */}
      <div className="bg-white/[0.03] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl mb-6">
        <form onSubmit={handleSearchSubmit} className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.searchArticlesPlaceholder}
              className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-9 pr-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => loadData()}
            disabled={isLoading}
            title="Refresh"
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1 ${isLoading ? 'animate-spin text-white' : ''}`} />
            {t.btnRefresh}
          </Button>
        </form>
      </div>

      {error && (
        <Alert type="error" className="mb-6">
          {error}
        </Alert>
      )}

      {/* Articles List */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-16 text-neutral-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">{t.searchSearching}</p>
        </div>
      ) : filteredArticles.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08]">
          <BookOpen className="h-8 w-8 mx-auto text-neutral-500 mb-3" />
          <h3 className="text-sm font-semibold text-white">{t.noArticlesFound}</h3>
          <p className="text-xs text-neutral-400 mt-1 max-w-sm mx-auto">{t.noArticlesDesc}</p>
        </Card>
      ) : (
        <div className="space-y-3.5">
          {filteredArticles.map((art) => (
            <Card key={art.id} elevated hoverable className="p-5 border-white/[0.08]">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-medium text-white bg-white/10 px-2.5 py-0.5 rounded-lg border border-white/20">
                    KB #{art.id}
                  </span>
                  {art.source_ticket_id && (
                    <Badge variant="neutral" size="sm">
                      {t.kbLinkedTicket} #{art.source_ticket_id}
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-1.5 text-xs text-neutral-400">
                  <Calendar className="h-3 w-3" />
                  <span>{new Date(art.created_at).toLocaleDateString()}</span>
                </div>
              </div>

              {/* Question */}
              <div className="mt-3">
                <h3 className="text-sm font-semibold text-white flex items-start gap-2">
                  <HelpCircle className="h-4 w-4 text-white shrink-0 mt-0.5" />
                  <span>{art.question}</span>
                </h3>
              </div>

              {/* Solution */}
              <div className="mt-2.5 pl-6 text-xs text-neutral-200 leading-relaxed whitespace-pre-line">
                {art.solution}
              </div>

              {/* Keywords */}
              {art.keywords && (
                <div className="mt-3.5 pt-3 border-t border-white/[0.08] flex flex-wrap items-center gap-1.5 pl-6">
                  <Tag className="h-3 w-3 text-neutral-500 mr-1" />
                  {art.keywords.split(',').map((kw) => (
                    <span
                      key={kw.trim()}
                      className="rounded-lg bg-white/[0.06] border border-white/[0.1] px-2 py-0.5 text-[11px] text-neutral-300"
                    >
                      {kw.trim()}
                    </span>
                  ))}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Modal: Ingest New Article (Admin Only) */}
      {isAdmin && isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-3.5 sm:p-4 bg-black/80 backdrop-blur-md">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-black/95 border border-white/[0.12] p-5 sm:p-6 shadow-2xl relative">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute right-4 top-4 text-neutral-400 hover:text-white"
            >
              <X className="h-5 w-5" />
            </button>

            <h3 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
              <Plus className="h-4 w-4 text-white" />
              {t.ingestModalTitle}
            </h3>
            <p className="text-xs text-neutral-400 mb-4">{t.ingestModalSub}</p>

            {modalError && (
              <Alert type="error" className="mb-4">
                {modalError}
              </Alert>
            )}

            {ingestSuccess && (
              <Alert type="success" className="mb-4">
                {locale === 'fr' ? 'Fiche ajoutée avec succès !' : 'Guide successfully added!'}
              </Alert>
            )}

            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  {t.inputQuestion}
                </label>
                <input
                  type="text"
                  required
                  placeholder={locale === 'fr' ? 'ex: Comment restaurer un portefeuille avec la clé secrète ?' : 'e.g. How to restore a wallet from seed?'}
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  {t.inputSolution}
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder={locale === 'fr' ? 'Procédure détaillée, étapes numérotées...' : 'Detailed instructions, steps...'}
                  value={newSolution}
                  onChange={(e) => setNewSolution(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-neutral-400 mb-1">
                  {t.inputKeywords}
                </label>
                <input
                  type="text"
                  placeholder={t.kbKeywordsPlaceholder}
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3 py-2 text-xs text-white placeholder-neutral-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/[0.08]">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsModalOpen(false)}
                  disabled={isIngesting}
                >
                  {t.btnCancel}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  size="sm"
                  isLoading={isIngesting}
                >
                  {t.btnSaveArticle}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
