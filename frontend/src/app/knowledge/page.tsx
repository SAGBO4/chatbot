'use client';

import React, { useState, useEffect, useRef } from 'react';
import { api } from '@/lib/api';
import { KnowledgeArticle } from '@/types';
import { useTranslation } from '@/lib/i18n/LanguageContext';
import { useTelegram } from '@/lib/telegram/TelegramContext';
import { useToast } from '@/components/ui/Toast';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/Dialog';
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
  Clock,
  ThumbsUp,
  ThumbsDown,
  Copy,
  Check,
  ChevronRight,
} from 'lucide-react';
import Link from 'next/link';

export default function KnowledgePage() {
  const { t, locale } = useTranslation();
  const { isAdmin, triggerHaptic } = useTelegram();
  const { toast } = useToast();

  const [articles, setArticles] = useState<KnowledgeArticle[]>([]);
  const [search, setSearch] = useState('');
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Article Reading Modal
  const [activeArticle, setActiveArticle] = useState<KnowledgeArticle | null>(null);
  const [feedbackGiven, setFeedbackGiven] = useState<'yes' | 'no' | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);

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

  // Extract all unique tags
  const allKeywords = Array.from(
    new Set(
      articles
        .flatMap((a) => (a.keywords ? a.keywords.split(',').map((k) => k.trim()) : []))
        .filter(Boolean)
    )
  ).slice(0, 10);

  const filteredArticles = articles.filter((art) => {
    const query = search.toLowerCase();
    const matchText =
      !query ||
      art.question.toLowerCase().includes(query) ||
      art.solution.toLowerCase().includes(query) ||
      (art.keywords && art.keywords.toLowerCase().includes(query));

    const matchTag =
      !selectedTag ||
      (art.keywords && art.keywords.toLowerCase().includes(selectedTag.toLowerCase()));

    return matchText && matchTag;
  });

  // Calculate estimated read time from word count
  const calculateReadTime = (text: string) => {
    const words = text.trim().split(/\s+/).length;
    const minutes = Math.max(1, Math.ceil(words / 150));
    return `${minutes} ${t.kbReadTime}`;
  };

  const handleOpenArticle = (art: KnowledgeArticle) => {
    triggerHaptic('light');
    setActiveArticle(art);
    setFeedbackGiven(null);
    setCopiedLink(false);
  };

  const handleCopyArticleLink = (artId: number) => {
    triggerHaptic('light');
    const url = `${window.location.origin}/knowledge#kb-${artId}`;
    navigator.clipboard?.writeText(url);
    setCopiedLink(true);
    toast({
      title: t.kbLinkCopied,
      description: `KB #${artId}`,
      variant: 'success',
    });
    setTimeout(() => setCopiedLink(false), 2000);
  };

  const handleFeedback = (type: 'yes' | 'no') => {
    triggerHaptic('medium');
    setFeedbackGiven(type);
    toast({
      title: t.kbHelpfulRecorded,
      description: type === 'yes' ? 'Ravi d’avoir pu vous aider !' : 'Nous continuons d’améliorer la documentation.',
      variant: 'success',
    });
  };

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
      toast({
        title: locale === 'fr' ? 'Guide publié' : 'Guide published',
        description: newQuestion.trim(),
        variant: 'success',
      });
      setNewQuestion('');
      setNewSolution('');
      setNewKeywords('');
      loadData();
      setTimeout(() => {
        setIsModalOpen(false);
        setIngestSuccess(false);
      }, 1200);
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || t.errKbAdd;
      setModalError(msg);
    } finally {
      setIsIngesting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 lg:py-12">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white mb-2.5 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>{t.navSupport}</span>
          </Link>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold tracking-tight text-white">
              {isAdmin ? t.kbTitle : (locale === 'fr' ? 'Base de Connaissances Officielle' : 'Official Knowledge Base')}
            </h1>
            <span
              className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium shadow-sm ${
                isAdmin
                  ? 'bg-white/10 border-white/20 text-white'
                  : 'bg-white/10 border-white/20 text-white'
              }`}
            >
              {isAdmin ? 'Admin • Documentation' : (locale === 'fr' ? 'Procédures Certifiées' : 'Certified Procedures')}
            </span>
          </div>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1 max-w-xl font-normal leading-relaxed">{t.kbSub}</p>
        </div>

        {isAdmin && (
          <Button
            variant="primary"
            size="sm"
            className="w-full sm:w-auto justify-center shadow-lg shadow-white/10"
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

      {/* Stats Cards - Wide 3-column Layout */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-5 mb-8">
        <Card elevated className="p-4 sm:p-5 border-white/[0.08] flex items-center gap-4 bg-[#0c0c0f]">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] shrink-0">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xl sm:text-2xl font-bold text-white tracking-tight">{articles.length}</div>
            <div className="text-xs text-zinc-300 font-medium">
              {isAdmin ? t.statTotalArticles : (locale === 'fr' ? 'Procédures documentées' : 'Documented guides')}
            </div>
          </div>
        </Card>

        <Card elevated className="p-4 sm:p-5 border-white/[0.08] flex items-center gap-4 bg-[#0c0c0f]">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] shrink-0">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xl sm:text-2xl font-bold text-white tracking-tight">100%</div>
            <div className="text-xs text-zinc-300 font-medium">
              {isAdmin ? t.statResolvedTickets : (locale === 'fr' ? 'Validation cryptographique' : 'Verified procedures')}
            </div>
          </div>
        </Card>

        <Card elevated className="p-4 sm:p-5 border-white/[0.08] flex items-center gap-4 bg-[#0c0c0f]">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.06] text-white border border-white/[0.12] shrink-0">
            <ShieldCheck className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="text-xl sm:text-2xl font-bold text-white tracking-tight">Stack v2.x</div>
            <div className="text-xs text-zinc-300 font-medium">
              {isAdmin ? t.statCoverage : (locale === 'fr' ? 'Version officielle active' : 'Official release')}
            </div>
          </div>
        </Card>
      </div>

      {/* Search Bar & Tag Chips */}
      <div className="bg-[#0c0c0f] backdrop-blur-2xl border border-white/[0.08] p-4 rounded-2xl mb-8 space-y-3.5 shadow-xl">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400 pointer-events-none" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t.searchArticlesPlaceholder}
              className="w-full rounded-xl bg-white/[0.04] backdrop-blur-md border border-white/[0.1] pl-10 pr-3 py-2 text-xs sm:text-sm text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none focus:ring-1 focus:ring-white/20"
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
            <span>{t.btnRefresh}</span>
          </Button>
        </div>

        {allKeywords.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            <span className="text-xs text-zinc-400 mr-1">{locale === 'fr' ? 'Thèmes :' : 'Topics:'}</span>
            {selectedTag && (
              <button
                type="button"
                onClick={() => setSelectedTag(null)}
                className="px-2 py-0.5 rounded-lg bg-white/10 text-white text-xs font-medium flex items-center gap-1 hover:bg-white/20 transition-colors cursor-pointer"
              >
                <span>{locale === 'fr' ? 'Tous' : 'All'}</span>
                <X className="h-3 w-3" />
              </button>
            )}
            {allKeywords.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setSelectedTag(selectedTag === tag ? null : tag)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                  selectedTag === tag
                    ? 'bg-white text-black font-semibold shadow-sm'
                    : 'bg-white/[0.04] border border-white/[0.08] text-zinc-300 hover:border-white/25 hover:text-white'
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}
      </div>

      {error && <Alert type="error" className="mb-6">{error}</Alert>}

      {/* Articles: 2-Column Responsive Grid on Desktop */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-20 text-zinc-400">
          <RefreshCw className="h-6 w-6 animate-spin text-white mb-3" />
          <p className="text-xs">{t.searchSearching}</p>
        </div>
      ) : filteredArticles.length === 0 ? (
        <Card elevated className="p-12 text-center border-white/[0.08] bg-[#0c0c0f]">
          <BookOpen className="h-8 w-8 mx-auto text-zinc-500 mb-3" />
          <h3 className="text-sm font-semibold text-white">{t.noArticlesFound}</h3>
          <p className="text-xs text-zinc-400 mt-1 max-w-sm mx-auto">{t.noArticlesDesc}</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {filteredArticles.map((art) => (
            <Card
              key={art.id}
              elevated
              hoverable
              onClick={() => handleOpenArticle(art)}
              className="p-6 border-white/[0.08] flex flex-col justify-between bg-[#0c0c0f] cursor-pointer transition-all group"
            >
              <div>
                <div className="flex items-center justify-between gap-2 pb-3.5 border-b border-white/[0.08]">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-semibold text-white bg-white/10 px-2.5 py-0.5 rounded-lg border border-white/20">
                      KB #{art.id}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-300 bg-white/[0.08] border border-white/[0.12] px-2 py-0.5 rounded">
                      <CheckCircle2 className="h-3 w-3" />
                      <span>{t.kbVerified}</span>
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-zinc-400">
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3 text-zinc-500" />
                      <span>{calculateReadTime(art.solution)}</span>
                    </span>
                  </div>
                </div>

                {/* Question / Title */}
                <div className="mt-4">
                  <h3 className="text-sm sm:text-base font-semibold text-white flex items-start gap-2.5 leading-snug group-hover:text-white transition-colors">
                    <HelpCircle className="h-4 w-4 text-zinc-400 shrink-0 mt-0.5" />
                    <span>{art.question}</span>
                  </h3>
                </div>

                {/* Solution Text Preview */}
                <div className="mt-3 text-xs sm:text-sm text-zinc-300 leading-relaxed font-normal line-clamp-3">
                  {art.solution}
                </div>
              </div>

              {/* Card Footer: Keywords & Action */}
              <div className="mt-5 pt-3.5 border-t border-white/[0.08] flex items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-1.5 overflow-hidden">
                  {art.keywords && (
                    <div className="flex items-center gap-1">
                      <Tag className="h-3 w-3 text-zinc-500 shrink-0" />
                      {art.keywords
                        .split(',')
                        .slice(0, 3)
                        .map((kw) => (
                          <span
                            key={kw.trim()}
                            className="rounded-lg bg-white/[0.04] border border-white/[0.08] px-2 py-0.5 text-[10px] text-zinc-300"
                          >
                            {kw.trim()}
                          </span>
                        ))}
                    </div>
                  )}
                </div>

                <span className="text-xs text-zinc-400 group-hover:text-white flex items-center gap-1 shrink-0 font-medium transition-colors">
                  <span>{locale === 'fr' ? 'Lire la fiche' : 'Read guide'}</span>
                  <ChevronRight className="h-3.5 w-3.5 group-hover:translate-x-0.5 transition-transform" />
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Detailed Article Reading Modal */}
      {activeArticle && (
        <Dialog open={Boolean(activeArticle)} onOpenChange={(open) => !open && setActiveArticle(null)}>
          <DialogContent onClose={() => setActiveArticle(null)} className="max-w-3xl bg-[#0c0c0f]">
            <DialogHeader>
              <div className="flex items-center justify-between gap-3 pb-3 border-b border-white/[0.08]">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-white bg-white/10 px-2.5 py-1 rounded-lg border border-white/20">
                    KB #{activeArticle.id}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs font-medium text-zinc-300 bg-white/[0.08] border border-white/[0.12] px-2.5 py-0.5 rounded">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>{t.kbVerified}</span>
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCopyArticleLink(activeArticle.id)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/[0.04] border border-white/[0.1] text-xs text-zinc-300 hover:text-white transition-colors cursor-pointer"
                    title={t.kbCopyLink}
                  >
                    {copiedLink ? <Check className="h-3.5 w-3.5 text-zinc-200" /> : <Copy className="h-3.5 w-3.5" />}
                    <span>{locale === 'fr' ? 'Copier le lien' : 'Copy link'}</span>
                  </button>
                </div>
              </div>

              <div className="pt-3">
                <DialogTitle className="text-lg sm:text-xl font-bold leading-snug text-white">
                  {activeArticle.question}
                </DialogTitle>
                <div className="flex items-center gap-3 text-xs text-zinc-400 mt-2">
                  <span className="flex items-center gap-1">
                    <Clock className="h-3.5 w-3.5 text-zinc-500" />
                    <span>{calculateReadTime(activeArticle.solution)}</span>
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5 text-zinc-500" />
                    <span>{new Date(activeArticle.created_at).toLocaleDateString()}</span>
                  </span>
                </div>
              </div>
            </DialogHeader>

            {/* Article Solution Content */}
            <div className="py-4 space-y-4">
              <div className="rounded-2xl bg-white/[0.02] border border-white/[0.08] p-5 sm:p-6 text-xs sm:text-sm text-zinc-200 leading-relaxed whitespace-pre-line font-normal space-y-3">
                {activeArticle.solution}
              </div>

              {activeArticle.keywords && (
                <div className="flex flex-wrap items-center gap-1.5 pt-2">
                  <span className="text-xs text-zinc-500 mr-1">Tags :</span>
                  {activeArticle.keywords.split(',').map((kw) => (
                    <span
                      key={kw.trim()}
                      className="rounded-lg bg-white/[0.04] border border-white/[0.08] px-2.5 py-0.5 text-xs text-zinc-300"
                    >
                      {kw.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Helpful Feedback Box */}
            <div className="mt-4 p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex flex-col sm:flex-row items-center justify-between gap-3">
              <span className="text-xs text-zinc-300 font-medium">
                {t.kbHelpfulQuestion}
              </span>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleFeedback('yes')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    feedbackGiven === 'yes'
                      ? 'bg-white text-black font-semibold shadow-md'
                      : 'bg-white/[0.04] border border-white/[0.08] text-zinc-300 hover:text-white hover:bg-white/[0.08]'
                  }`}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                  <span>{t.kbHelpfulYes}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleFeedback('no')}
                  className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                    feedbackGiven === 'no'
                      ? 'bg-zinc-700 text-white font-semibold'
                      : 'bg-white/[0.04] border border-white/[0.08] text-zinc-300 hover:text-white hover:bg-white/[0.08]'
                  }`}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                  <span>{t.kbHelpfulNo}</span>
                </button>
              </div>
            </div>

            <DialogFooter>
              <Button variant="secondary" size="sm" onClick={() => setActiveArticle(null)}>
                {locale === 'fr' ? 'Fermer la fiche' : 'Close'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Modal: Ingest New Article (Admin Only) */}
      {isAdmin && isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md">
          <div className="w-full max-w-lg max-h-[90vh] overflow-y-auto rounded-2xl bg-[#0a0e17] border border-white/[0.12] p-6 shadow-2xl relative">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute right-4 top-4 text-zinc-400 hover:text-white cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>

            <h3 className="text-base font-semibold text-white mb-1 flex items-center gap-2">
              <Plus className="h-4 w-4 text-white" />
              {t.ingestModalTitle}
            </h3>
            <p className="text-xs text-zinc-400 mb-4">{t.ingestModalSub}</p>

            {modalError && <Alert type="error" className="mb-4">{modalError}</Alert>}
            {ingestSuccess && (
              <Alert type="success" className="mb-4">
                {locale === 'fr' ? 'Guide ajouté avec succès !' : 'Guide successfully added!'}
              </Alert>
            )}

            <form onSubmit={handleIngest} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  {t.inputQuestion}
                </label>
                <input
                  type="text"
                  required
                  placeholder={locale === 'fr' ? 'ex: Comment restaurer un portefeuille avec la clé secrète ?' : 'e.g. How to restore a wallet from seed?'}
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  {t.inputSolution}
                </label>
                <textarea
                  rows={4}
                  required
                  placeholder={locale === 'fr' ? 'Procédure détaillée, étapes numérotées...' : 'Detailed instructions, steps...'}
                  value={newSolution}
                  onChange={(e) => setNewSolution(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">
                  {t.inputKeywords}
                </label>
                <input
                  type="text"
                  placeholder={t.kbKeywordsPlaceholder}
                  value={newKeywords}
                  onChange={(e) => setNewKeywords(e.target.value)}
                  className="w-full rounded-xl bg-white/[0.04] border border-white/[0.1] px-3.5 py-2 text-xs text-white placeholder-zinc-500 focus:border-white/40 focus:outline-none"
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
